"""Core monitoring loop and maintenance orchestration.

This module implements the main monitoring loop, snapshot emission and the
periodic maintenance tasks (rotation, compression and cleanup). The implementation
keeps runtime orchestration concise to ease testing and reuse.
"""

import logging

from .emitter import emit_snapshot as _emit_snapshot

from ..system.logs import ensure_log_dirs_exist
from ..system.maintenance import _read_maintenance_intervals, _run_maintenance
from ..monitoring.state import SystemState
from ..config.settings import get_valid_thresholds
from ..monitoring.metrics import collect_metrics as _collect_metrics
from ..monitoring.averages import ensure_last_ts_exists

_NO_DATA_STR = "No data"

# Maintenance helpers are provided by `src.system.maintenance` (imported above).


# ---------------------------------------------------------------------------
# Helper and orchestration notes
# ---------------------------------------------------------------------------
# This module focuses on runtime orchestration: collecting metrics, emitting
# snapshots and scheduling periodic maintenance. Helper implementations are
# intentionally kept small and imported from their respective packages so
# unit tests can exercise logic in isolation.


# ---------------------------------------------------------------------------
# Main monitoring loop
# ---------------------------------------------------------------------------


def run_loop(interval: float, cycles: int, verbose_level: int) -> None:
    """Run the main monitoring loop: collect metrics and run maintenance tasks.

    Args:
        interval: Delay between cycles in seconds.
        cycles: Number of cycles to run (0 = run indefinitely).
        verbose_level: Controls human-facing output verbosity (0 = silent).

    The function performs light runtime checks before each cycle, collects
    metrics, emits snapshots and schedules periodic maintenance tasks. Heavy
    failures in maintenance or collection are logged but do not stop the loop.

    """
    import time

    # Validate recommended minimum interval to avoid excessive load
    if interval < 0.1:
        logging.getLogger(__name__).warning(
            "Interval too small (%.2fs). Recommended >= 0.1s to avoid overload", interval
        )

    thresholds = get_valid_thresholds()
    state = SystemState(thresholds)
    # Note: the argument parser already applies environment overrides where
    # appropriate (priority: CLI > ENV > default). Do not re-read environment
    # variables here so CLI-provided values are not overwritten.
    executed = 0
    intervals = _read_maintenance_intervals()
    last_rotate = 0.0
    last_compress = 0.0
    last_safe_remove = 0.0
    last_hourly = 0.0
    try:
        while True:
            _ensure_runtime_checks()
            cycle_start = time.monotonic()
            _collect_and_emit(state, verbose_level)
            cycle_elapsed = time.monotonic() - cycle_start
            if cycle_elapsed > 1.0:
                logging.getLogger(__name__).warning("Slow cycle: %.2fs (expected < 1.0s)", cycle_elapsed)
            now = time.monotonic()
            try:
                last_rotate, last_compress, last_safe_remove, last_hourly = _run_maintenance(
                    now, last_rotate, last_compress, last_safe_remove, last_hourly, intervals
                )
            except Exception as exc:
                # Best-effort: log maintenance scheduling errors at debug level
                logging.getLogger(__name__).debug("Failed to schedule maintenance: %s", exc, exc_info=True)
            executed += 1
            if cycles != 0 and executed >= cycles:
                break
            if interval > 0.0:
                try:
                    time.sleep(interval)
                except Exception as exc:
                    # Sleep interruptions are non-fatal; log at debug level for diagnostics
                    logging.getLogger(__name__).debug("Sleep interrupted: %s", exc, exc_info=True)
    except KeyboardInterrupt:
        # Respect user interrupt and exit gracefully
        logging.info("KeyboardInterrupt received, exiting...")


def _ensure_runtime_checks() -> None:
    """Perform lightweight runtime checks before each collection cycle.

    Ensures logging directories exist and the ``last_ts`` control file is present.
    Failures are handled in a best-effort manner and logged at debug level so
    the main loop is not interrupted by non-critical I/O errors.
    """
    try:
        ensure_log_dirs_exist()
    except Exception as exc:
        # Do not fail the main loop on lightweight I/O issues; record for debugging
        logging.getLogger(__name__).debug("ensure_log_dirs_exist failed: %s", exc, exc_info=True)
    try:
        ensure_last_ts_exists()
    except Exception as exc:
        # Best-effort last_ts verification; log debug and continue
        logging.getLogger(__name__).debug("ensure_last_ts_exists failed: %s", exc, exc_info=True)


def _collect_and_emit(state: SystemState, verbose_level: int) -> dict:
    """Collect metrics, evaluate system state and emit a snapshot.

    Returns a result dict with keys ``'state'`` and ``'metrics'`` suitable for
    logging and downstream consumers. Metric collection is best-effort and
    falls back to an empty mapping on failure. Post-evaluation treatments are
    triggered for metrics that exceed configured thresholds.
    """
    try:
        metrics = _collect_metrics()
    except Exception:
        metrics = {}

        # Daily network-usage learning: attempt to record bytes sent/received
        # for the learning model when collection fails partially. This is
        # best-effort and must not raise.
        try:
            from src.monitoring.handlers import network_learning_handler

            bytes_sent = metrics.get("bytes_sent")
            bytes_recv = metrics.get("bytes_recv")
            if bytes_sent is not None and bytes_recv is not None:
                # Ensure arguments are integers before recording
                try:
                    bs = int(float(bytes_sent))
                    br = int(float(bytes_recv))
                    network_learning_handler.record_daily_usage(bs, br)
                except (ValueError, TypeError):
                    pass
        except Exception as exc:
            logging.getLogger(__name__).debug("Failed to record daily network learning: %s", exc, exc_info=True)

    state_name = state.evaluate_metrics(metrics)
    # After evaluating metrics, check and attempt treatments for critical metrics
    from src.monitoring.handlers import attempt_treatment

    thresholds = getattr(state, "thresholds", {})
    for metric_name, limits in thresholds.items():
        crit = limits.get("critical")
        value = metrics.get(metric_name)
        if crit is not None and value is not None and value >= crit:
            # Trigger configured treatments for metrics that exceed critical limits.
            # The treatment subsystem decides the concrete action and side-effects.
            attempt_treatment(state, metric_name, {"value": value, "threshold": crit})
    result = {"state": state_name, "metrics": metrics}
    snapshot = getattr(state, "current_snapshot", None)
    _emit_snapshot(snapshot if isinstance(snapshot, dict) else None, result, verbose_level)

    # Log de ciclo completo em modo verbose
    if verbose_level >= 2:
        logging.getLogger(__name__).info("Cycle complete: %d metrics collected, state=%s", len(metrics), state_name)

    return result


# Keep a private alias for backward compatibility: some internal code/tests may
# reference ``_run_loop``.
_run_loop = run_loop
