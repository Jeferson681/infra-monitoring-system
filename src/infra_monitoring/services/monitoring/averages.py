"""Aggregate averages and persist aggregated statistics.

Utilities to iterate monitoring JSONL files, aggregate time windows, compute
per-metric averages and counts, and produce human-readable output lines used
by maintenance routines and reports. Implementations are resilient to I/O
errors and designed to remain compatible with existing test APIs.
"""

import datetime
import json
import logging
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from infra_monitoring.infra.system.logs import write_log
from infra_monitoring.infra.system.time_helpers import extract_epoch

from .formatters import (
    _build_long_from_metrics,
    _fmt_bytes_human,
    format_duration,
    format_used_files_lines,
)
from .state import compute_metric_states

# imports kept minimal; avoid unused imports that ruff flags

# do not import iter_jsonl_objects from averages (may be removed); decode JSONL inline


def _find_candidate_files(root: Path, pattern_prefix: str = "monitoring") -> list[Path]:
    """Find possible locations of JSONL files for a given filename pattern.

    Parameters
    ----------
    root : Path
        The root directory to search under.
    pattern_prefix : str, optional
        File prefix to search for (default: 'monitoring').

    Returns
    -------
    List[Path]
        Candidate file paths to check for today's JSONL.

    """
    t = datetime.date.today().strftime("%Y-%m-%d")
    return [
        root / "logs" / "json" / pattern_prefix / f"{pattern_prefix}-{t}.jsonl",
        root / "logs" / "json" / f"{pattern_prefix}-{t}.jsonl",
        root / "json" / pattern_prefix / f"{pattern_prefix}-{t}.jsonl",
        root / "json" / f"{pattern_prefix}-{t}.jsonl",
    ]


def _iter_jsonl_file(
    path: Path, max_retries: int = 3
) -> Iterator[tuple[dict, Path, int]]:
    """Yield JSON objects from a single file path, skipping malformed lines.

    Uses retries with exponential backoff to handle files being written.
    """
    for attempt in range(max_retries):
        try:
            with path.open("r", encoding="utf-8") as fh:
                for lineno, ln in enumerate(fh, start=1):
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        obj = json.loads(ln)
                    except json.JSONDecodeError:
                        # ignore malformed JSON lines
                        continue
                    if isinstance(obj, dict):
                        yield obj, path, lineno
            return  # Success, exit
        except OSError as exc:
            if attempt < max_retries - 1:
                # Retry with exponential backoff
                wait_time = 0.1 * (2**attempt)
                logging.getLogger(__name__).debug(
                    "_iter_jsonl_file: attempt %d/%d failed, waiting %.2fs: %s",
                    attempt + 1,
                    max_retries,
                    wait_time,
                    exc,
                )
                time.sleep(wait_time)
            else:
                # Last attempt failed
                logging.getLogger(__name__).error(
                    "_iter_jsonl_file: failed after %d attempts: %s",
                    max_retries,
                    exc,
                    exc_info=True,
                )
                raise
        except Exception as exc:
            logging.getLogger(__name__).error(
                "_iter_jsonl_file: unexpected failure %s", exc, exc_info=True
            )


def _iter_jsonl_today(logs_root: Path) -> Iterator[tuple[dict, Path, int]]:
    """Iterate valid JSON objects from today's files in candidate locations.

    Open candidate files and decode each JSON line (ignores invalid lines).
    """
    for c in _find_candidate_files(logs_root):
        if not c.exists():
            continue
        yield from _iter_jsonl_file(c)


# --- Extracted helpers for epoch parsing (moved to module level to reduce
# complexity inside _extract_epoch)


def _compute_averages_and_counts(window: list[tuple], metric_keys: list[str]) -> tuple[
    dict[str, float | None],
    dict[str, int],
    dict[str, dict[str, int]],
    dict[str, int],
]:
    """Compute sums, counts, averages and counts_by_state for a given window.

    Returns (averages, counts, counts_by_state_per_metric, state_counts).
    """
    sums: dict[str, float] = dict.fromkeys(metric_keys, 0.0)
    counts: dict[str, int] = dict.fromkeys(metric_keys, 0)
    counts_by_state_per_metric: dict[str, dict[str, int]] = {k: {} for k in metric_keys}
    state_counts: dict[str, int] = {}

    for o, _ts, _p, _ln in window:
        _process_window_item(
            o, metric_keys, sums, counts, counts_by_state_per_metric, state_counts
        )

    averages: dict[str, float | None] = {}
    for k in metric_keys:
        cnt = counts.get(k, 0) or 0
        if cnt == 0:
            averages[k] = None
        else:
            averages[k] = sums.get(k, 0.0) / float(cnt)

    return averages, counts, counts_by_state_per_metric, state_counts


def _process_window_item(
    o: dict,
    metric_keys: list[str],
    sums: dict[str, float],
    counts: dict[str, int],
    counts_by_state_per_metric: dict[str, dict[str, int]],
    state_counts: dict[str, int],
) -> None:
    """Process a single window item and update aggregates in-place.

    Extracted to reduce complexity of the aggregator while preserving logic.
    """
    rel = extract_relevant(o)
    st_global = _normalize_state(rel.get("state"))
    if st_global is not None:
        state_counts[st_global] = state_counts.get(st_global, 0) + 1

    # Use compute_metric_states (centralized in state.py) to obtain individual states
    metrics_for_state = {k: rel.get(k) for k in metric_keys}
    # keep compatibility; can be updated to pass real thresholds
    thresholds: dict[str, dict[str, Any]] = {}
    metric_states = compute_metric_states(metrics_for_state, thresholds)

    # Mapping of metric to individual state field (consistent with state.py)
    state_field_map = {
        "cpu_percent": "state_cpu",
        "memory_used_bytes": "state_ram",
        "disk_used_bytes": "state_disk",
        "ping_ms": "state_ping",
        "latency_ms": "state_latency",
        "bytes_sent": "state_bytes_sent",
        "bytes_recv": "state_bytes_recv",
    }

    for k in metric_keys:
        v = rel.get(k)
        if v is None:
            continue
        try:
            num = float(v)
        except (TypeError, ValueError):
            continue
        sums[k] = sums.get(k, 0.0) + num
        counts[k] = (counts.get(k, 0) or 0) + 1
        # Individual metric state, if present
        st_metric = None
        state_field = state_field_map.get(k)
        if state_field and metric_states.get(state_field):
            st_metric = _normalize_state(metric_states.get(state_field))
        else:
            st_metric = st_global
        if st_metric is not None:
            d = counts_by_state_per_metric.get(k) or {}
            d[st_metric] = d.get(st_metric, 0) + 1
            counts_by_state_per_metric[k] = d


def _compute_state_durations(
    sorted_window: list[tuple],
) -> tuple[dict[str, float], dict[str, str]]:
    state_durations: dict[str, float] = {}

    for i in range(len(sorted_window) - 1):
        o_curr, ts_curr, _, _ = sorted_window[i]
        _, ts_next, _, _ = sorted_window[i + 1]
        dur = ts_next - ts_curr
        st = _normalize_state(extract_relevant(o_curr).get("state"))
        if st is None:
            continue
        state_durations[st] = state_durations.get(st, 0.0) + float(dur)

    # Use centralized formatter for durations to keep presentation consistent
    state_durations_human: dict[str, str] = (
        {k: format_duration(v) for k, v in state_durations.items()}
        if state_durations
        else {}
    )
    return state_durations, state_durations_human


def _compute_time_from_to(window: list[tuple]) -> tuple[str, str]:
    """Return (time_from_iso, time_to_iso) for the given window of (o, ts, p, ln).

    Small helper to keep aggregate_last_seconds simpler.
    """
    time_from = datetime.datetime.fromtimestamp(
        min(ts for (_, ts, __, ___) in window), tz=datetime.UTC
    ).isoformat()
    time_to = datetime.datetime.fromtimestamp(
        max(ts for (_, ts, __, ___) in window), tz=datetime.UTC
    ).isoformat()
    return time_from, time_to


def _build_used_files_lines(window: list[tuple]) -> dict[str, tuple[int, int]]:
    used_files: dict[str, tuple[int, int]] = {}
    for _o, _ts, p, ln in window:
        k = str(p)
        if k in used_files:
            cur_min, cur_max = used_files[k]
            if ln < cur_min:
                cur_min = ln
            if ln > cur_max:
                cur_max = ln
            used_files[k] = (cur_min, cur_max)
        else:
            used_files[k] = (ln, ln)
    return used_files


def extract_relevant(obj: dict) -> dict[str, Any]:
    """Extract relevant fields from a log object for aggregation.

    Returns a dictionary with 'state' and raw metrics mapped to predictable
    keys used by the aggregator and formatters.

    Note: historically the aggregator looked for `metrics_raw` while the
    current emitter writes `metrics` in the JSONL. To be resilient to both
    shapes prefer `metrics` and fall back to `metrics_raw`.
    """
    # Prefer 'metrics' (written by the feed) and fall back to 'metrics_raw' if absent
    m = obj.get("metrics") or obj.get("metrics_raw") or {}
    # Also extract individual states if present
    return {
        "state_cpu": obj.get("state_cpu"),
        "state_ram": obj.get("state_ram"),
        "state_disk": obj.get("state_disk"),
        "state_ping": obj.get("state_ping"),
        "state_latency": obj.get("state_latency"),
        "state_bytes_sent": obj.get("state_bytes_sent"),
        "state_bytes_recv": obj.get("state_bytes_recv"),
        "cpu_percent": m.get("cpu_percent"),
        "cpu_freq_ghz": m.get("cpu_freq_ghz"),
        "memory_percent": m.get("memory_percent"),
        "memory_used_bytes": m.get("memory_used_bytes"),
        "memory_total_bytes": m.get("memory_total_bytes"),
        "disk_percent": m.get("disk_percent"),
        "disk_used_bytes": m.get("disk_used_bytes"),
        "disk_total_bytes": m.get("disk_total_bytes"),
        "bytes_sent": m.get("bytes_sent"),
        "bytes_recv": m.get("bytes_recv"),
        "ping_ms": m.get("ping_ms"),
        "latency_ms": m.get("latency_ms"),
        "temperature_celsius": m.get("temperature_celsius"),
        "bytes_sent_human": (
            _fmt_bytes_human(int(m["bytes_sent"]))
            if m.get("bytes_sent") is not None
            else None
        ),
        "bytes_recv_human": (
            _fmt_bytes_human(int(m["bytes_recv"]))
            if m.get("bytes_recv") is not None
            else None
        ),
    }


def _normalize_state(s: str | None) -> str | None:
    """Normalize state strings to canonical uppercase values.

    Examples: 'CRITICAL' or 'CRIT' -> 'CRITICAL'; 'WARN' -> 'WARNING'.
    Returns None when the input is falsy.
    """
    if not s:
        return None
    try:
        su = str(s).strip().upper()
    except Exception:
        return None
    if su in ("CRITICAL", "CRIT"):
        return "CRITICAL"
    if su in ("WARN", "WARNING"):
        return "WARNING"
    return su


def aggregate_last_seconds(logs_root: Path, seconds: int = 10) -> dict[str, Any] | None:
    """Aggregate metrics from the last `seconds` seconds from today's JSONL files.

    Returns a dict containing averages, counts and metadata, or None if no
    valid data is available. Designed to be resilient to invalid JSON lines.
    """
    objs: list[tuple[dict, Path, int]] = list(_iter_jsonl_today(logs_root))
    if not objs:
        return None

    # extract timestamps and keep valid items (defensive unpack)
    items: list[tuple[dict, float, Path, int]] = []
    for entry in objs:
        try:
            o, src_path, src_ln = entry
        except ValueError:
            continue
        ts = extract_epoch(o)
        if ts is not None:
            items.append((o, ts, src_path, src_ln))
    if not items:
        return None

    # window: from the largest timestamp back `seconds`
    last_ts = max(ts for (_, ts, __, ___) in items)
    cutoff = last_ts - float(seconds)

    window = [(o, ts, p, ln) for (o, ts, p, ln) in items if cutoff <= ts <= last_ts]
    if not window:
        return None

    n_lines = len(window)

    metric_keys = (
        "cpu_percent",
        "cpu_freq_ghz",
        "memory_percent",
        "memory_used_bytes",
        "memory_total_bytes",
        "disk_percent",
        "disk_used_bytes",
        "disk_total_bytes",
        "bytes_sent",
        "bytes_recv",
        "ping_ms",
        "latency_ms",
        "temperature_celsius",
    )

    # Compute averages, counts and per-state counts using helper
    averages, counts, counts_by_state_per_metric, state_counts = (
        _compute_averages_and_counts(window, list(metric_keys))
    )

    # compute state durations using helper
    sorted_window = sorted(window, key=lambda x: x[1])
    state_durations, state_durations_human = _compute_state_durations(sorted_window)

    time_from, time_to = _compute_time_from_to(window)

    result: dict[str, Any] = {
        "window_seconds": seconds,
        "n_lines": n_lines,
        "time_from": time_from,
        "time_to": time_to,
        "averages": averages,
        "state_counts": state_counts or None,
        "state_durations": state_durations or None,
        "state_durations_human": state_durations_human or None,
        "counts_per_metric": counts,
        "counts_per_metric_by_state": counts_by_state_per_metric,
    }

    # build used files/lines map using helper
    try:
        used_files = _build_used_files_lines(window)
        if used_files:
            result["used_files_lines"] = used_files
    except Exception as exc:
        logging.getLogger(__name__).debug(
            "aggregate used_files_lines build failed: %s", exc, exc_info=True
        )

    # human readable for bytes averages
    _add_human_bytes(result["averages"])

    _safe_persist_last_time(last_ts=last_ts)

    return result


def _add_human_bytes(averages: dict[str, Any]) -> None:
    """Add human-readable (GB) fields to the averages dictionary when applicable."""
    try:
        if averages.get("bytes_sent") is not None:
            averages["bytes_sent_human"] = _fmt_bytes_human(int(averages["bytes_sent"]))
        if averages.get("bytes_recv") is not None:
            averages["bytes_recv_human"] = _fmt_bytes_human(int(averages["bytes_recv"]))
    except Exception:
        logging.getLogger(__name__).debug("_add_human_bytes failed", exc_info=True)


def _safe_persist_last_time(last_ts: float) -> None:
    """Persist last_ts to a file without propagating exceptions to the caller.

    Logs at debug level on failure and continues in best-effort mode.
    """
    try:
        persist_last_time(last_ts=last_ts)
    except Exception as exc:
        logging.getLogger(__name__).debug(
            "persist_last_time failed: %s", exc, exc_info=True
        )


def format_long_metric_from_aggregate(aggregate: dict[str, Any]) -> str:
    """Build a long_metric string (multiple lines) from aggregate result.

    Uses formatters._build_long_from_metrics to produce the list of lines,
    then joins them with newlines and returns a single string.
    """
    metrics_src = _build_metrics_src_from_aggregate(aggregate)

    # Delegate to existing formatter to build lines
    try:
        lines = _build_long_from_metrics(metrics_src)
    except Exception:
        # fallback: simple key: value lines
        lines = [f"{k}: {v}" for k, v in metrics_src.items()]

    # Keep metric lines raw (do not add arrow decorations or suffixes)
    out_lines = list(lines)

    # If used_files_lines present, format into human-friendly lines
    try:
        used = (
            aggregate.get("used_files_lines") if isinstance(aggregate, dict) else None
        )
        if used:
            out_lines.extend(format_used_files_lines(used))
    except Exception as exc:
        logging.getLogger(__name__).debug(
            "format_long_metric_from_aggregate used_files_lines section failed: %s",
            exc,
            exc_info=True,
        )

    return "\n".join(out_lines)


# vulture: ignore
# NOTE: The functions `extract_window_entries`, `get_fixed_log_path` and
# `_format_used_files_lines` were intentionally removed as part of a
# cleanup: their behavior overlapped with other public APIs and they were
# only used by tests. If needed in the future, their implementations can
# be restored from version control.


def _build_metrics_src_from_aggregate(aggregate: dict[str, Any]) -> dict[str, Any]:
    """Build the metrics_src dict used by format_long_metric_from_aggregate.

    Copies averages and converts time_to ISO to epoch when possible.
    """
    metrics_src: dict[str, Any] = {}
    avgs = aggregate.get("averages") or {}
    for k, v in avgs.items():
        metrics_src[k] = v

    ts_iso = aggregate.get("time_to")
    if ts_iso:
        # Delegate parsing to centralized helper to support many timestamp formats
        try:
            from infra_monitoring.infra.system.time_helpers import (
                extract_epoch as _extract_epoch,
            )  # local import

            parsed = (
                _extract_epoch({"time_to": ts_iso})
                if not isinstance(ts_iso, (int, float))
                else float(ts_iso)
            )
            metrics_src["timestamp"] = parsed if parsed is not None else ts_iso
        except Exception:
            metrics_src["timestamp"] = ts_iso

    return metrics_src


# Decoration helpers removed: metric lines are output without arrow decorations


def write_average_log(
    aggregate: dict[str, Any],
    human_enable: bool = True,
    json_enable: bool = False,
    safe_log_enable: bool = True,
    log: bool = True,
    hourly: bool = True,
    hourly_window_seconds: int = 10,
    name: str = "average_metric",
) -> None:
    """Format aggregate as long_metric and write via system.write_log and to fixed file.

    - Builds the long_metric using `format_long_metric_from_aggregate`.
        - Calls `write_log(name, 'INFO', message, ..., human_enable=..., json_enable=...,
            safe_log_enable=..., log=..., hourly=..., hourly_window_seconds=...)`.
        - Also appends the same human text to a fixed file at `logs/log/{name}.log`.
    """
    human_text = format_long_metric_from_aggregate(aggregate)

    # Delegate safe datestamped write to the logging subsystem which will
    # preserve multiline human text when safe_log_enable=True (see
    # src/system/logs.py change). This centralizes file naming and avoids
    # duplicate datestamped files being created by both subsystems.
    try:
        write_log(
            name=name,
            level="INFO",
            message=human_text,
            extra=None,
            human_enable=bool(human_enable),
            json_enable=json_enable,
            safe_log_enable=safe_log_enable,
            log=log,
            hourly=hourly,
            hourly_window_seconds=hourly_window_seconds,
        )
    except Exception as exc:
        # do not crash if logging subsystem fails; log debug
        logging.getLogger(__name__).debug("write_log failed: %s", exc, exc_info=True)


# _compute_suffix_for_metric_key removed (no longer used)


def get_last_ts_file(name: str = "last_ts") -> Path:
    """Return the Path for the last_ts JSON file and ensure its parent exists.

    If `logs_root` is None, resolve from the logging subsystem so the cache
    lives under the same `logs_root` used by `get_log_paths()`.
    """
    # Create the file inside .cache at the project root
    from infra_monitoring.infra.system.helpers import get_project_root

    cache_dir = get_project_root() / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{name}.json"


def persist_last_time(last_ts: float | None = None, name: str = "last_ts") -> Path:
    """Persist a small JSON object with the last timestamp (epoch and ISO).

    Overwrites the file with a compact JSON object. If `last_ts` is None,
    use the current UTC timestamp.
    """
    if last_ts is None:
        last_ts = datetime.datetime.now(datetime.UTC).timestamp()

    entry = {
        "last_time": float(last_ts),
        "last_time_iso": datetime.datetime.fromtimestamp(
            last_ts, tz=datetime.UTC
        ).isoformat(),
    }

    fpath = get_last_ts_file(name=name)
    try:
        with fpath.open("w", encoding="utf-8") as fh:
            json.dump(entry, fh, ensure_ascii=False)
    except PermissionError as exc:
        logging.getLogger(__name__).warning(
            "persist_last_time: permission denied creating %s: %s",
            fpath,
            exc,
            exc_info=True,
        )
        # best-effort: try append via write_text as fallback
        try:
            from infra_monitoring.infra.system.log_helpers import write_text

            write_text(fpath, json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            # best-effort fallback: ignore errors when attempting append fallback
            # nosec B110 - intentional swallow: persistence is best-effort here
            pass
    except OSError as exc:
        logging.getLogger(__name__).error(
            "persist_last_time: failed writing %s: %s", fpath, exc, exc_info=True
        )
    return fpath


def read_last_time(name: str = "last_ts") -> float | None:
    """Read the JSON file and return the numeric `last_time` (epoch) or None."""
    fpath = get_last_ts_file(name=name)
    if not fpath.exists():
        return None
    try:
        with fpath.open("r", encoding="utf-8") as fh:
            obj = json.load(fh)
        v = obj.get("last_time")
        if v is None:
            return None
        return float(v)
    except (OSError, TypeError, ValueError) as exc:
        logging.getLogger(__name__).error(
            "read_last_time: failed reading %s: %s", fpath, exc, exc_info=True
        )
        return None


# Lightweight helper: ensure the last_ts file exists at runtime
def ensure_last_ts_exists(name: str = "last_ts") -> None:
    """Ensure the control file `last_ts` exists at runtime.

    Performs a quick check; if the file does not exist, calls
    `persist_last_time()` to create the file in the provided `logs_root`
    (or the default resolved by `get_last_ts_file`). Designed to be
    called frequently by the loop with minimal overhead.
    """
    logger = logging.getLogger(__name__)
    try:
        fpath = get_last_ts_file(name=name)
    except Exception as exc:
        logger.error(
            "ensure_last_ts_exists: failed to resolve path: %s", exc, exc_info=True
        )
        return

    if not fpath.exists():
        try:
            # persist_last_time ensures the parent directory is created when needed
            persist_last_time(last_ts=None, name=name)
            logger.debug("ensure_last_ts_exists: created %s", fpath)
        except Exception as exc:
            logger.error(
                "ensure_last_ts_exists: failed to create %s: %s",
                fpath,
                exc,
                exc_info=True,
            )


def ensure_default_last_ts() -> None:
    """Ensure the default last_ts file exists and contains a non-zero timestamp.

    This function centralizes o que rodava no import. Deve ser chamada pelo entrypoint
    durante o startup para evitar I/O no import.
    """
    try:
        existing = read_last_time()
    except Exception:
        existing = None

    if existing is None or abs(float(existing) - 0.0) <= 1e-9:
        try:
            persist_last_time()
        except Exception as exc:
            logging.getLogger(__name__).debug(
                "persist_last_time on startup init failed: %s", exc, exc_info=True
            )
            # Persist current timestamp (persist_last_time ensures the directory)
            try:
                persist_last_time()
            except Exception as exc:
                # fallback: log debug but do not raise
                logging.getLogger(__name__).debug(
                    "persist_last_time on startup init failed: %s", exc, exc_info=True
                )
