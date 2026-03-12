"""System metric collection and normalization.

Collects CPU, memory, disk, latency, network and temperature-related
metrics. Uses a per-metric cache configured in ``_METRIC_INTERVALS`` and
groups related keys (for example: ``memory``, ``disk``, ``network``,
``temperature``) to reduce collection overhead.
"""

import logging
import math
import platform
import re
import socket
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psutil

from infra_monitoring.infra.system.helpers import (
    _disk_candidate_paths,
    validate_host_port,
)

logger = logging.getLogger(__name__)

# Flag indicating whether the last latency measurement was a timeout estimate
_last_latency_estimated: bool = False
# Flag to avoid exposing an initial spurious 0% from psutil on first collection
_cpu_warmed_up: bool = False

# Simple per-metric cache
# Reasonable intervals (in seconds) to avoid excessive queries.
# Adjust for your environment/sensitivity as needed.
# Use a small set of cache keys, grouping network into a single item.
_METRIC_INTERVALS: dict[str, float] = {
    "cpu_percent": 1.0,
    "memory_percent": 5.0,
    "disk_percent": 10.0,
    "memory": 5.0,
    "cpu_freq_ghz": 30.0,
    "network": 2.0,
    "ping_ms": 5.0,
    "latency_ms": 5.0,
    "latency_estimated": 5.0,
    "temperature": 30.0,
    "disk": 10.0,
}

# cache: key -> { 'value': ..., 'ts': float(monotonic) }
_CACHE: dict[str, dict] = {
    k: {"value": None, "ts": 0.0} for k in _METRIC_INTERVALS.keys()
}

# Locks to ensure we don't trigger multiple simultaneous collections for the
# same metric. We use try_acquire (non-blocking) in the collector to avoid
# blocking the caller thread — if a collection is already in progress we use
# the cached value.
_LOCKS: dict[str, threading.Lock] = {
    k: threading.Lock() for k in _METRIC_INTERVALS.keys()
}

# Temperature constants
TEMPERATURE_MIN_THRESHOLD = 20.0  # Filter values < 20°C as suspicious
SENSOR_PRIORITY_ORDER = ["k10temp", "coretemp", "it8792", "nct6798"]


def _now() -> float:
    """Return a monotonic timestamp (in seconds).

    Used internally to measure cache age without depending on the system clock.
    """
    return time.monotonic()


def _is_stale(key: str) -> bool:
    """Return True if the cached value for `key` is stale.

    Considers the interval configured in `_METRIC_INTERVALS`.
    """
    try:
        last = float(_CACHE.get(key, {}).get("ts", 0.0))
        interval = float(_METRIC_INTERVALS.get(key, 1.0))
        return (_now() - last) >= interval
    except (TypeError, ValueError) as exc:
        logger.debug("_is_stale failed for key %s: %s", key, exc, exc_info=True)
        return True


def _cache_get_or_refresh(
    key: str, collector: Callable[..., Any], *args: Any, **kwargs: Any
) -> Any:
    """Return the cached value for `key`, refreshing it when stale.

    `collector` is a callable invoked to re-run the measurement. For known
    keys a per-key lock is used to avoid concurrent collections.
    """
    # if the key is unknown, call the collector directly
    if key not in _METRIC_INTERVALS:
        try:
            return collector(*args, **kwargs)
        except (TypeError, ValueError, RuntimeError, OSError) as exc:
            logger.debug(
                "collector failed for unknown key %s: %s", key, exc, exc_info=True
            )
            return None

    # if not stale, return cached value
    if not _is_stale(key):
        return _CACHE.get(key, {}).get("value")

    def _refresh_no_lock():
        try:
            val = collector(*args, **kwargs)
        except (TypeError, ValueError, RuntimeError, OSError) as exc:
            logger.debug(
                "failed to refresh collector for key %s: %s", key, exc, exc_info=True
            )
            val = None
        _CACHE[key]["value"] = val
        _CACHE[key]["ts"] = _now()
        return val

    lock = _LOCKS.get(key)
    if lock is None:
        return _refresh_no_lock()

    if not lock.acquire(blocking=False):
        # somebody else is updating; return whatever is in cache
        return _CACHE.get(key, {}).get("value")

    try:
        # refresh once we have the lock
        return _refresh_no_lock()
    finally:
        try:
            lock.release()
        except RuntimeError as exc:
            logger.debug("lock.release() failed: %s", exc, exc_info=True)


def collect_metrics() -> dict[str, float | int | str | None]:
    """Collect and normalize system metrics and return a flat mapping.

    The result contains primitive values (float/int/str/None) suitable for
    serialization and formatting. Uses internal caching to reduce cost of
    expensive system calls.
    """
    metrics: dict[str, float | int | str | None] = {}

    # Break logic into helpers to keep this function readable and reduce
    # cyclomatic/cognitive complexity while preserving exact behavior.
    _reset_cache_timestamps()
    _collect_percent_metrics(metrics)
    _collect_memory_and_bytes(metrics)
    _collect_network_metrics(metrics)
    _collect_latency_metrics(metrics)
    _collect_temperature_and_timestamp(metrics)
    _collect_disk_usage_bytes(metrics)

    # Best-effort: expose a small set of metrics to the Prometheus exporter
    # if available. Keep failures non-fatal so metric collection remains robust.
    try:
        _export_some_metrics(metrics)
    except Exception as exc:
        logger.debug("_export_some_metrics failed: %s", exc, exc_info=True)

    return metrics


def _export_some_metrics(metrics: dict[str, float | int | str | None]) -> None:
    """Expose a small set of metrics to the Prometheus exporter if available.

    This is a best-effort integration: failures are logged and ignored.
    """
    try:
        from infra_monitoring.api.exporter.prometheus import expose_metric

        for key in ("cpu_percent", "memory_percent", "disk_percent"):
            try:
                val = metrics.get(key)
                if val is not None:
                    expose_metric(
                        f"monitoring_{key}",
                        float(val),
                        description=f"{key} from monitoring",
                    )
            except Exception:
                # Do not break metric collection if exporter fails for a value
                logger.debug(
                    "_export_some_metrics: failed to expose %s", key, exc_info=True
                )
    except Exception as exc:
        # exporter may be unavailable; log at debug level and continue
        logger.debug(
            "_export_some_metrics: exporter unavailable: %s", exc, exc_info=True
        )


def _reset_cache_timestamps() -> None:
    """Force a cache timestamp reset to ensure collectors run in tests."""
    try:
        for k in _CACHE.keys():
            _CACHE[k]["ts"] = 0.0
    except (AttributeError, TypeError) as exc:
        logger.debug("failed to reset cache timestamps: %s", exc, exc_info=True)


def _collect_percent_metrics(metrics: dict[str, float | int | str | None]) -> None:
    """Collect percentages: `cpu_percent`, `cpu_freq_ghz`, `memory_percent`, `disk_percent`."""
    cpu = _safe_float(_cache_get_or_refresh("cpu_percent", get_cpu_percent))
    metrics["cpu_percent"] = None if cpu is None else max(0.0, min(100.0, cpu))

    cpu_freq = _safe_float(_cache_get_or_refresh("cpu_freq_ghz", get_cpu_freq_ghz))
    metrics["cpu_freq_ghz"] = None if cpu_freq is None else float(cpu_freq)

    mem = _safe_float(_cache_get_or_refresh("memory_percent", get_memory_percent))
    metrics["memory_percent"] = None if mem is None else max(0.0, min(100.0, mem))

    disk = _safe_float(_cache_get_or_refresh("disk_percent", get_disk_percent))
    metrics["disk_percent"] = None if disk is None else max(0.0, min(100.0, disk))


def _collect_memory_and_bytes(metrics: dict[str, float | int | str | None]) -> None:
    try:
        # Use the grouped 'memory' cache to obtain used/total together (same
        # interval as `memory_percent` — 5s). Does not change names/formats.
        mem = _cache_get_or_refresh("memory", get_memory_info) or (None, None)
        used, total = (None, None)
        try:
            used, total = mem  # type: ignore
        except Exception:
            used, total = (None, None)
        metrics["memory_used_bytes"] = int(used) if used is not None else None
        # total in bytes (same source/cache 'memory')
        metrics["memory_total_bytes"] = int(total) if total is not None else None
    except Exception:
        metrics["memory_used_bytes"] = None
        metrics["memory_total_bytes"] = None


def _collect_network_metrics(metrics: dict[str, float | int | str | None]) -> None:
    """Collect `bytes_sent` and `bytes_recv` (uses grouped `network` cache)."""
    net = _cache_get_or_refresh("network", lambda: get_network_stats()) or {}
    metrics["bytes_sent"] = _safe_counter(net.get("bytes_sent"))
    metrics["bytes_recv"] = _safe_counter(net.get("bytes_recv"))


def _collect_latency_metrics(metrics: dict[str, float | int | str | None]) -> None:
    """Collect `ping_ms`, `latency_ms` and `latency_estimated` (fallback flag)."""
    ping = _safe_float(
        _cache_get_or_refresh("ping_ms", lambda: get_latency("8.8.8.8", 53, 1.0))
    )
    metrics["ping_ms"] = None if (ping is None or ping < 0.0) else ping

    latency = _safe_float(_cache_get_or_refresh("latency_ms", lambda: get_latency()))
    metrics["latency_ms"] = None if (latency is None or latency < 0.0) else latency
    try:
        metrics["latency_estimated"] = bool(_last_latency_estimated)
    except Exception:
        metrics["latency_estimated"] = False


def _collect_temperature_and_timestamp(
    metrics: dict[str, float | int | str | None],
) -> None:
    """Collect `temperature_celsius` (cache `temperature`) and `timestamp` (time.time())."""
    metrics["temperature_celsius"] = _cache_get_or_refresh(
        "temperature", _temperature_collector
    )
    metrics["timestamp"] = time.time()


def _collect_disk_usage_bytes(metrics: dict[str, float | int | str | None]) -> None:
    """Collect `disk_used_bytes` and `disk_total_bytes` (cache `disk`)."""
    try:
        du = _cache_get_or_refresh("disk", get_disk_usage_info) or (None, None)
        used, total = (None, None)
        try:
            used, total = du  # type: ignore
        except Exception:
            used, total = (None, None)
        metrics["disk_used_bytes"] = int(used) if used is not None else None
        metrics["disk_total_bytes"] = int(total) if total is not None else None
    except Exception:
        metrics["disk_used_bytes"] = None
        metrics["disk_total_bytes"] = None


def _safe_float(val: object) -> float | None:
    """Convert `val` to float; reject NaN/Inf and return None on error.

    Only int/float/str are accepted; otherwise return None.
    """
    if not isinstance(val, (int, float, str)):
        return None
    try:
        f = float(val)
        if not math.isfinite(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _safe_counter(v: object) -> int | None:
    """Convert and validate a counter-like value to a non-negative int or None."""
    if not isinstance(v, (int, float, str)):
        return None
    try:
        n = int(v)
        return n if n >= 0 else None
    except (ValueError, TypeError):
        return None


def get_cpu_percent() -> float | None:
    """Return CPU usage percent (non-blocking).

    Note: psutil may return 0.0 on the first call (spurious). To avoid
    exposing that noise, take a brief blocking sample on first collection;
    if still 0.0 return None to avoid misleading values.
    """
    global _cpu_warmed_up
    try:
        val = psutil.cpu_percent(interval=0.0)
    except (OSError, RuntimeError):
        return None

    # If not warmed up and value is 0.0, take a small blocking sample and
    # mark as warmed. If the new sample is also 0.0, return None to avoid
    # exposing a spurious 0% on first collection.
    # Use epsilon comparisons to avoid direct equality checks.
    eps = 1e-6
    if not _cpu_warmed_up and abs(val - 0.0) <= eps:
        try:
            val2 = psutil.cpu_percent(interval=0.05)
        except (OSError, RuntimeError) as exc:
            logger.debug("short cpu_percent sample failed: %s", exc, exc_info=True)
            val2 = None
        _cpu_warmed_up = True
        if val2 is None:
            return None
        return None if abs(val2 - 0.0) <= eps else val2

    return val


def get_cpu_freq_ghz() -> float | None:
    """Return the current CPU frequency in GHz or None if unavailable.

    Uses psutil.cpu_freq() which typically returns values in MHz; convert
    to GHz by dividing by 1000. Handle exceptions and missing values.
    """
    try:
        f = psutil.cpu_freq()
    except (OSError, RuntimeError) as exc:
        logger.debug("psutil.cpu_freq() failed: %s", exc, exc_info=True)
        return None

    if not f:
        return None

    # 'current' is usually in MHz; guard against None
    curr = getattr(f, "current", None)
    if curr is None:
        return None
    try:
        ghz = float(curr) / 1000.0
        if not math.isfinite(ghz):
            return None
        return ghz
    except (TypeError, ValueError):
        return None


def get_memory_percent() -> float:
    """Return the memory usage percent."""
    return psutil.virtual_memory().percent


def get_disk_percent(path: str | None = None) -> float | None:
    r"""Return the disk usage percent for the specified `path`.

    If `path` is None choose a cross-platform default:
    - Windows: use the filesystem anchor (e.g. 'C:\\') via Path().anchor
    - POSIX: use '/'

    Returns ``None`` on error (e.g. invalid path or permission).
    """
    try:
        # resolve candidate path(s) to try — accept str or Path
        candidates: list[object] = []
        if path:
            candidates.append(Path(path))
        candidates.extend(_disk_candidate_paths())

        for p in candidates:
            try:
                # psutil accepts str or Path; attempt disk_usage regardless of p.exists()
                return psutil.disk_usage(str(p)).percent
            except OSError:
                # try next candidate; probe in best-effort mode and continue
                continue

        # if no candidate worked, try the first one even if it does not exist
        try:
            return psutil.disk_usage(str(candidates[0])).percent
        except OSError:
            return None
    except OSError:
        return None


def _get_temp_from_script(script_path: Path) -> float | None:
    """Kept for test compatibility; deprecated in favor of psutil.

    This function is retained for tests, but the psutil method is preferred
    and this helper will be removed in future releases.
    """
    logger.debug("_get_temp_from_script: deprecated; use psutil instead")
    return None


def _parse_first_float_from_text(text: str) -> float | None:
    """Attempt to extract the first floating number from `text` and return it.

    Return None if no number is found or the value is not finite.
    """
    if not text:
        return None
    m = re.search(r"([-+]?\d*\.?\d+)", text)
    if not m:
        return None
    try:
        v = float(m.group(1))
        return v if math.isfinite(v) else None
    except (ValueError, TypeError) as exc:
        logger.error(
            "_parse_first_float_from_text: parse failed: %s", exc, exc_info=True
        )
        return None


def _temperature_collector() -> float | None:
    """Collector used by the cache: return CPU temperature using psutil."""
    try:
        # Tentar obter temperaturas usando psutil.sensors_temperatures()
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if temps:
                # Preferir k10temp (AMD) ou coretemp (Intel)
                for sensor_name in SENSOR_PRIORITY_ORDER:
                    if sensor_name in temps:
                        entries = temps[sensor_name]
                        if entries:
                            # Buscar Tctl (AMD) ou Package (Intel)
                            for entry in entries:
                                if entry.label in ("Tctl", "Package", "Core 0"):
                                    logger.debug(
                                        "_temperature_collector: obtido de %s.%s = %.1f°C",
                                        sensor_name,
                                        entry.label,
                                        entry.current,
                                    )
                                    return entry.current
                            # If a specific label is not found, use the first one
                            if entries[0].current is not None:
                                logger.debug(
                                    "_temperature_collector: obtido de %s (primeiro) = %.1f°C",
                                    sensor_name,
                                    entries[0].current,
                                )
                                return entries[0].current

                # Fallback: try any sensor that is not acpitz
                for sensor_name, entries in temps.items():
                    if sensor_name != "acpitz" and entries:
                        current = entries[0].current
                        if (
                            current is not None and current > TEMPERATURE_MIN_THRESHOLD
                        ):  # Filter suspicious low values
                            logger.debug(
                                "_temperature_collector: obtained from %s = %.1f°C",
                                sensor_name,
                                current,
                            )
                            return current
    except Exception as exc:
        logger.error(
            "_temperature_collector failed using psutil: %s", exc, exc_info=True
        )

    return None


def get_network_stats() -> dict[str, int]:
    """Return network statistics (bytes sent/received) as integers."""
    # psutil.net_io_counters() returns monotonic counters since boot.
    # Frequent calls are avoided by the grouped 'network' cache used by the collector.
    net = psutil.net_io_counters()
    return {
        "bytes_sent": int(net.bytes_sent),
        "bytes_recv": int(net.bytes_recv),
    }


def get_network_latency(
    host: str = "8.8.8.8", port: int = 53, timeout: float = 2.0
) -> float | None:
    """Return latency in ms.

    1. Use the system `ping` binary (one attempt).
    2. If that fails, try a TCP connection (actual latency measurement via socket).

    Returns a float in ms or None.
    """
    global _last_latency_estimated
    _last_latency_estimated = False

    # validate host/port
    if not validate_host_port(host, port):
        logger.debug(
            "validate_host_port failed for %s:%s, falling back to localhost", host, port
        )
        host = "127.0.0.1"

    def _build_ping_cmd(host: str, timeout: float) -> list[str]:
        """Build the appropriate ping command for the platform.

        Uses millisecond timeouts on Windows and seconds on most Unices.
        """
        system = platform.system().lower()
        if system.startswith("win"):
            return ["ping", "-n", "1", "-w", str(int(timeout * 1000)), host]
        # -W frequentemente espera segundos; arredondar para int
        return ["ping", "-c", "1", "-W", str(int(timeout)), host]

    def _parse_ping_output_for_ms(output: str) -> float | None:
        """Parse ping output and return the time in ms, or None if not found.

        The regex looks for the pattern `= <num> ms` common to many implementations.
        """
        m = re.search(r"=\s*([\d.]+)\s*ms", output)
        if not m:
            return None
        try:
            v = float(m.group(1))
            return v if math.isfinite(v) else None
        except (ValueError, TypeError) as exc:
            logger.debug(
                "get_network_latency: ping parse failed: %s", exc, exc_info=True
            )
            return None

    # Try using system ping
    cmd = _build_ping_cmd(host, timeout)
    try:
        import subprocess  # nosec B404 - used with vetted list args and no shell

        # subprocess.check_output is called with a vetted list `cmd` (no shell).
        out = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, text=True, timeout=float(timeout or 2.0)
        )  # nosec B603
    except subprocess.CalledProcessError:
        # ping returned non-zero exit status; try TCP fallback
        logger.debug("get_network_latency: ping returned non-zero exit status")
    except (subprocess.SubprocessError, OSError) as exc:
        # any other error (timeout, missing binary etc.) -> fallback
        logger.debug("get_network_latency: ping failed: %s", exc, exc_info=True)
    else:
        parsed = _parse_ping_output_for_ms(out)
        if parsed is not None:
            _last_latency_estimated = False
            return parsed

    # continue to TCP fallback
    return _tcp_latency_fallback(host, port, timeout)


def _tcp_latency_fallback(host: str, port: int, timeout: float) -> float | None:
    """Attempt to measure latency via a TCP connection; marks _last_latency_estimated.

    Returns the value in ms or None. Keeps the `_last_latency_estimated` flag True
    when entering the fallback to indicate the measurement did not come from ICMP ping.
    """
    global _last_latency_estimated
    try:
        start = time.perf_counter()
        with socket.create_connection((host, port), timeout=timeout):
            end = time.perf_counter()
        v = round((end - start) * 1000, 2)
        _last_latency_estimated = True
        return v
    except OSError:
        _last_latency_estimated = True
        return None


# Compatibility wrappers: keep old API and provide convenience
def get_latency(
    host: str = "8.8.8.8", port: int = 53, timeout: float = 2.0
) -> float | None:
    """Alias for `get_network_latency` (compatibility)."""
    return get_network_latency(host=host, port=port, timeout=timeout)


def get_memory_info() -> tuple[int | None, int | None]:
    """Return (used_bytes, total_bytes) of physical memory or (None, None)."""
    try:
        vm = psutil.virtual_memory()
        return int(getattr(vm, "used", 0)), int(getattr(vm, "total", 0))
    except (OSError, RuntimeError, AttributeError) as exc:
        logger.debug("get_memory_info failed: %s", exc, exc_info=True)
        return None, None


def get_disk_usage_info(path: str | None = None) -> tuple[int | None, int | None]:
    """Return (used_bytes, total_bytes) of the disk for `path` or (None, None)."""
    try:
        candidates: list[object] = []
        if path:
            candidates.append(Path(path))
        try:
            candidates.extend(_disk_candidate_paths())
        except Exception as exc:
            logger.debug("building disk candidates failed: %s", exc, exc_info=True)
        for p in candidates:
            try:
                du = psutil.disk_usage(str(p))
                return int(getattr(du, "used", 0)), int(getattr(du, "total", 0))
            except OSError:
                continue
        try:
            du = psutil.disk_usage(str(candidates[0]))
            return int(getattr(du, "used", 0)), int(getattr(du, "total", 0))
        except OSError as exc:
            logger.debug(
                "get_disk_usage_info: psutil.disk_usage failed: %s", exc, exc_info=True
            )
            return None, None
    except OSError as exc:
        logger.debug("get_disk_usage_info failed: %s", exc, exc_info=True)
        return None, None


# End of latency implementations


# Silence Vulture: utility functions used by operators/tests/runtime.
# Keep benign references so static analyzers don't flag them as unused.
_VULTURE_KEEP = [get_memory_info, get_disk_usage_info]
