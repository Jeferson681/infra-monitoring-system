"""Format metrics for human consumption.

Normalize raw metrics and produce short and detailed summaries suitable for
console output. This module provides the public `normalize_for_display`
API used by the emission helpers.
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def normalize_for_display(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize raw metrics into a structure ready for display.

    Returns a dict containing `summary_short`, `summary_long` and
    `metrics_raw`.
    """
    summary_short = _build_short_from_metrics(metrics)
    long_lines = _build_long_from_metrics(metrics)

    return {
        "summary_short": summary_short,
        "summary_long": long_lines,
        "metrics_raw": metrics,
    }


# Helper for normalize_for_display — build short summary (-v)
def _build_short_from_metrics(metrics: Dict[str, Any]) -> str:
    """Build a concise, human-readable short summary from metrics.

    Includes CPU, RAM, ping and disk when available. Returns a no-data
    placeholder when no metrics are present.
    """
    cpu = metrics.get("cpu_percent")
    mem_percent = metrics.get("memory_percent")
    disk_percent = metrics.get("disk_percent")
    ping = metrics.get("ping_ms")
    parts: list[str] = []
    if cpu is not None:
        # include optional frequency (GHz) when available; show GHz before percent
        cpu_freq = metrics.get("cpu_freq_ghz")
        if cpu_freq is not None:
            try:
                cpu_freq_f = float(cpu_freq)
                parts.append(f"CPU {cpu_freq_f:.1f}GHz • {int(round(cpu))}%")
            except Exception:
                parts.append(f"CPU {int(round(cpu))}%")
        else:
            parts.append(f"CPU {int(round(cpu))}%")
    if mem_percent is not None:
        parts.append(f"RAM {int(round(mem_percent))}%")
    if ping is not None:
        parts.append(f"Ping {int(round(ping))} ms")
    if disk_percent is not None:
        parts.append(f"Disk {int(round(disk_percent))}%")
    return " | ".join(parts) if parts else "No data"


# Helper for normalize_for_display — build detailed lines (-vv)
def _build_long_from_metrics(metrics: Dict[str, Any]) -> list[str]:
    r"""Generate detailed metric lines for full display.

    Shows CPU, RAM, Disk, Ping, Latency, Temperature, traffic and timestamp.
    Returns a list of strings ready to be joined with '\n'.
    """
    cpu = metrics.get("cpu_percent")
    mem_used = metrics.get("memory_used_bytes")
    mem_total = metrics.get("memory_total_bytes")
    disk_used = metrics.get("disk_used_bytes")
    disk_total = metrics.get("disk_total_bytes")
    ping = metrics.get("ping_ms")
    latency = metrics.get("latency_ms")
    long_lines: list[str] = []

    # CPU line: include frequency if available (GHz before percent)
    if cpu is not None:
        cpu_freq = metrics.get("cpu_freq_ghz")
        if cpu_freq is not None:
            try:
                cpu_freq_f = float(cpu_freq)
                long_lines.append(f"CPU: {cpu_freq_f:.1f}GHz • {int(round(cpu))}%")
            except Exception:
                long_lines.append(f"CPU: {int(round(cpu))}%")
        else:
            long_lines.append(f"CPU: {int(round(cpu))}%")
    else:
        long_lines.append("CPU: Unavailable")
    mem_line = _fmt_bytes_gb(mem_used, mem_total)
    long_lines.append(f"RAM: {mem_line}")
    disk_line = _fmt_bytes_gb(disk_used, disk_total)
    long_lines.append(f"Disk: {disk_line}")
    long_lines.append(f"Ping: {ping:.1f} ms" if ping is not None else "Ping: Unavailable")

    if latency is not None:
        # Always show latency in ms to avoid converting to seconds which may
        # hide that the value is a timeout/estimate (e.g. 10000 ms -> 10.0 s).
        long_lines.append(f"Latency: {latency:.1f} ms")
    else:
        long_lines.append("Latency: Unavailable")

    temp = metrics.get("temperature_celsius")
    long_lines.append(f"Temperature: {temp} C" if temp is not None else "Temperature: Unavailable")

    bytes_sent = metrics.get("bytes_sent")
    bytes_recv = metrics.get("bytes_recv")
    long_lines.append(f"Bytes sent: {_fmt_bytes_human(bytes_sent)}")
    long_lines.append(f"Bytes received: {_fmt_bytes_human(bytes_recv)}")

    # Append timestamp line using helper to keep complexity low
    long_lines.append(_format_timestamp_line(metrics.get("timestamp")))

    return long_lines


def _format_timestamp_line(ts_val) -> str:
    """Format the timestamp field into a human-readable line.

    Returns 'Date/time: Unavailable' when no timestamp is present, or a
    formatted representation when possible. On parse errors returns the raw value.
    """
    if ts_val is None:
        return "Date/time: Unavailable"
    try:
        # Delegate parsing to centralized time helper which accepts multiple formats
        from ..system.time_helpers import _parse_epoch_from_value  # type: ignore
        import datetime

        parsed = _parse_epoch_from_value(ts_val)
        if parsed is None:
            # fallback to raw representation when unable to parse
            return f"Date/time: {ts_val}"
        dt = datetime.datetime.fromtimestamp(float(parsed), tz=datetime.timezone.utc)
        return f"Date/time: {dt.strftime('%Y-%m-%d %H:%M:%S')}"
    except Exception as exc:
        logger.debug("invalid timestamp when formatting date/time: %s", exc, exc_info=True)
        return f"Date/time: {ts_val}"


# Helper for _build_long_from_metrics — convert bytes to GB/percent
def _fmt_bytes_gb(used: int | None, total: int | None) -> str:
    """Format byte usage in GB and show percentage.

    Returns 'Unavailable' when data is insufficient.
    """
    if used is None or total is None or total == 0:
        return "Unavailable"
    try:
        used_gb = used / (1024**3)
        total_gb = total / (1024**3)
        percent = int(round((used / total) * 100))
        return f"{used_gb:.1f} / {total_gb:.0f} GB • {percent}%"
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        logger = logging.getLogger(__name__)
        logger.debug("error formatting bytes to GB: %s", exc, exc_info=True)
        return "Unavailable"


# Helper: _build_long_from_metrics — format traffic in MB/GB
def _fmt_bytes_human(n: int | None) -> str:
    """Format bytes into MB/GB for human readability.

    Returns 'Unavailable' when the value is None or invalid.
    """
    if n is None:
        return "Unavailable"
    try:
        mb = n / (1024**2)
        gb = n / (1024**3)
        if gb >= 1.0:
            # Use two decimal places to match pre-existing expectations/tests
            return f"{gb:.2f} GB"
        # MB values also formatted with two decimals for consistency
        return f"{mb:.2f} MB"
    except (TypeError, ValueError) as exc:
        logger = logging.getLogger(__name__)
        logger.debug("error formatting bytes for human readable output: %s", exc, exc_info=True)
        return "Unavailable"


def format_duration(seconds: float) -> str:
    """Return duration formatted as H:MM:SS.

    Formats a duration given in seconds into H:MM:SS representation.
    Returns '0:00:00' on parse errors.
    """
    try:
        secs = int(round(float(seconds)))
    except Exception:
        return "0:00:00"
    import datetime

    return str(datetime.timedelta(seconds=secs))


def format_used_files_lines(used: dict) -> list[str]:
    """Return a formatted list of lines describing used files.

    Format the path->(min_line, max_line) dict into readable lines for
    display, preserving previous behavior of `averages._format_used_files_lines`.
    """
    out: list[str] = ["", "Used lines:"]
    from pathlib import Path

    for k in sorted(used.keys()):
        try:
            rng = used.get(k)
        except (AttributeError, TypeError):
            continue
        if not isinstance(rng, (list, tuple)) or len(rng) < 2:
            continue
        a, b = int(rng[0]), int(rng[1])
        try:
            fname = Path(k).name
        except Exception:
            fname = str(k)
        if a == b:
            out.append(f"{fname} line {a}")
        else:
            out.append(f"{fname} lines {a} to {b}")
    return out


def format_snapshot_human(snapshot: dict | None, result: dict) -> str:
    """Return a human-readable message for a snapshot/result.

    This function applies the same logic previously in core._format_human_msg:
    - prefer `summary_short` when available
    - otherwise join `summary_long` when present
    - otherwise delegate to `normalize_for_display(metrics)` to build a summary
    - fallback to 'state=<state>' when nothing else is available

    Returns a single string ready to be written to logs.
    """
    # Prefer explicit short summary from the snapshot when present.
    if isinstance(snapshot, dict):
        ss = snapshot.get("summary_short")
        if ss:
            return ss

        long_lines = snapshot.get("summary_long") or []
        if isinstance(long_lines, list) and long_lines:
            return "\n".join(str(x) for x in long_lines)

        metrics = snapshot.get("metrics")
        if isinstance(metrics, dict):
            nf = normalize_for_display(metrics)
            return nf.get("summary_short") or f"state={result.get('state')}"

        return f"state={result.get('state')}"

    return f"state={result.get('state')}"
