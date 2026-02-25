"""Snapshot emission helpers extracted from ``core``.

This module centralizes the responsibilities for formatting human-friendly
messages, printing short/long summaries to stdout and emitting canonical
JSON snapshots to the logging/ingestion subsystem. Keeping emission
logic separate reduces the responsibilities of the orchestration code and
improves testability of formatting and output behavior.
"""

import logging

# ruff: noqa: D401
from ..services.monitoring.formatters import normalize_for_display, format_snapshot_human
from ..infra.system.logs import write_log
from ..api.exporter.prometheus import expose_metric as _expose_metric

# Lightweight counter for snapshot emits
_APP_SNAPSHOT_EMITS = 0

_NO_DATA_STR = "No data"


def _format_human_msg(snapshot: dict | None, result: dict) -> str:  # noqa: D401
    """Return a human-readable message for the provided snapshot and result.

    Delegates to the centralized formatter when available. On unexpected
    formatting errors the function falls back to a minimal representation so
    the emission flow remains robust and does not raise.
    """
    try:
        return format_snapshot_human(snapshot, result)
    except Exception:
        return f"state={result.get('state')}"


def _print_snapshot_short(snap: dict | None) -> None:  # noqa: D401
    """Print a short, single-line snapshot summary to stdout.

    When an explicit short summary is not present the function attempts to
    derive a compact representation via the display normalizer. This helper
    is best-effort and must not raise for malformed input.
    """
    if not isinstance(snap, dict):
        print(_NO_DATA_STR)
        return

    summary_short = snap.get("summary_short")
    if summary_short:
        print(summary_short)
        return

    metrics = snap.get("metrics")
    if isinstance(metrics, dict):
        nf = normalize_for_display(metrics)
        print(nf.get("summary_short") or _NO_DATA_STR)
        return

    print(_NO_DATA_STR)


def _print_snapshot_long(snap: dict | None) -> None:  # noqa: D401
    """Print a multi-line, detailed snapshot summary to stdout.

    If an explicit long summary is not present the function attempts to
    derive a readable multi-line representation from normalized metrics.
    The implementation prefers explicit summaries when available because
    they may contain richer, human-authored context.
    """
    if not isinstance(snap, dict):
        print("SNAPSHOT: No data")
        return

    summary_long = snap.get("summary_long")
    if summary_long and isinstance(summary_long, list):
        for line in summary_long:
            print(line)
        return

    metrics = snap.get("metrics")
    if isinstance(metrics, dict):
        nf = normalize_for_display(metrics)
        long_lines = nf.get("summary_long") or []
        if isinstance(long_lines, list) and long_lines:
            for line in long_lines:
                print(line)
            return

    print("SNAPSHOT:", snap)


def emit_snapshot(snapshot: dict | None, result: dict, verbose_level: int) -> None:  # noqa: D401
    """Emit the canonical snapshot and optionally print human output.

    Side effects:
    - write the canonical JSON feed for ingestion (via ``write_log``)
    - optionally print a human-friendly short or long summary to stdout

    The function must be resilient: failures when formatting or writing the
    canonical feed are logged but do not raise. Human output is controlled
    by ``verbose_level`` to avoid noisy output in automated environments.
    """
    logger = logging.getLogger(__name__)

    try:
        human_msg = _format_human_msg(snapshot, result)
        try:
            # Write the canonical JSON feed used for monitoring ingestion.
            # Disable any additional human formatting for the ingestion path.
            write_log("monitoring", "INFO", human_msg, extra=snapshot, human_enable=False, json_enable=True)
            # increment and expose a lightweight emit counter
            try:
                global _APP_SNAPSHOT_EMITS
                _APP_SNAPSHOT_EMITS += 1
                _expose_metric("app_snapshot_emit_total", float(_APP_SNAPSHOT_EMITS), "Number of snapshot emits")
            except Exception:
                logging.getLogger(__name__).debug("Failed to expose snapshot emit metric", exc_info=True)
        except Exception as exc:
            logger.info("Failed to write log via write_log: %s", exc)
    except Exception:
        logger.info("Failed to build/emit snapshot", exc_info=True)

    if not verbose_level:
        return

    if verbose_level == 1:
        _print_snapshot_short(snapshot)
    else:
        _print_snapshot_long(snapshot)
