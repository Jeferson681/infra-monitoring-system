"""Helpers for exporting metrics in Prometheus format.

Expose system and process metrics as Prometheus Gauges when
``prometheus_client`` is available. When the optional dependency is
unavailable the functions are no-ops and log debug information instead.
"""

import json
import os
import time
import psutil
import logging
from typing import Dict, cast, Iterable, Tuple, Any

logger = logging.getLogger(__name__)

# Try to import prometheus_client; fall back to no-op if unavailable
_HAVE_PROM = False
_gauges: Dict[str, object] = {}
_server_started = False

try:
    from prometheus_client import Gauge  # type: ignore

    _HAVE_PROM = True
except Exception:  # pragma: no cover - optional dependency
    # Failed to import prometheus_client: Prometheus export will be disabled (optional)
    _HAVE_PROM = False


# Cache for _sanitize_metric_name() to avoid reprocessing identical names
_sanitize_cache: Dict[str, str] = {}


def _sanitize_metric_name(name: str) -> str:
    """Sanitize a metric name to the Prometheus format, replacing invalid characters with underscore."""
    # Check cache first
    if name in _sanitize_cache:
        return _sanitize_cache[name]

    # Prometheus metric names: [a-zA-Z_:][a-zA-Z0-9_:]*
    out = []
    for i, ch in enumerate(name):
        if i == 0:
            if ch.isalpha() or ch in ("_", ":"):
                out.append(ch)
            else:
                out.append("_")
        else:
            if ch.isalnum() or ch in ("_", ":"):
                out.append(ch)
            else:
                out.append("_")
    result = "".join(out)
    _sanitize_cache[name] = result
    return result


def start_exporter(port: int | None = None, addr: str | None = None) -> None:
    """Initialize exporter metrics without starting an HTTP server.

    NOTE: after refactor the HTTP server is provided by `main_http.run_http_server`.
    `start_exporter()` now only initializes/promotes metric registration and
    performs a best-effort initial population of Gauges from JSONL. It does NOT
    start any HTTP server to avoid bind conflicts; the HTTP server is the
    responsibility of `main_http` (primary).

    """
    global _server_started
    if _server_started:
        logger.debug("exporter Prometheus already initialized")
        return

    # Initialize metrics from JSONL (best-effort) so the registry contains
    # initial values when `generate_latest()` is called.
    try:
        jsonl_path = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "json")
        expose_system_metrics_from_jsonl(jsonl_path)
    except Exception:
        logger.debug("Failed to populate initial metrics from JSONL", exc_info=True)

    # Mark as initialized to avoid repeated work; this does NOT imply a server
    # was started.
    _server_started = True
    logger.info("Prometheus exporter initialized (no HTTP server started)")


def expose_metric(name: str, value: float, description: str = "") -> None:
    """Expose a numeric metric as a Prometheus Gauge.

    Creates the Gauge on first call and updates the value on subsequent calls.
    If `prometheus_client` is not available, logs and returns.
    """
    if not _HAVE_PROM:
        logger.debug("prometheus_client not available; expose_metric %s=%s ignored", name, value)
        return

    san = _sanitize_metric_name(name)
    try:
        if san not in _gauges:
            g = Gauge(san, description or f"Gauge for {name}")
            _gauges[san] = g
        else:
            g = _gauges[san]
        # Cast to Gauge for type checkers and call set
        g_cast = cast(Gauge, g)
        g_cast.set(float(value))
    except Exception as exc:
        logger.debug("Failed to expose metric %s: %s", name, exc, exc_info=True)


def expose_system_metrics_from_jsonl(jsonl_path: str) -> None:
    """Read the last line from JSONL and expose system metrics as Gauges."""
    if not _HAVE_PROM:
        return
    try:
        files = [f for f in os.listdir(jsonl_path) if f.startswith("monitoring-") and f.endswith(".jsonl")]
        if not files:
            return
        files.sort(reverse=True)
        latest_file = os.path.join(jsonl_path, files[0])
        with open(latest_file, "rb") as f:
            f.seek(0, os.SEEK_END)
            pos = f.tell()
            line = b""
            while pos > 0:
                pos -= 1
                f.seek(pos)
                char = f.read(1)
                if char == b"\n" and line:
                    break
                line = char + line
            last_json = line.decode("utf-8").strip()
        if last_json:
            metrics = json.loads(last_json)
            for k, v in metrics.items():
                if isinstance(v, (int, float)):
                    expose_metric(f"monitoring_{k}", float(v), f"System metric {k} from JSONL")
    except Exception as exc:
        logger.debug("Failed to expose system metrics from JSONL: %s", exc, exc_info=True)


def expose_process_metrics() -> None:
    """Expose current Python process metrics (CPU, RAM, uptime, threads) as Prometheus Gauges."""
    if not _HAVE_PROM:
        return
    try:
        proc = psutil.Process()
        # Collect and export process metrics:
        # - CPU percent
        cpu = proc.cpu_percent(interval=0.0)
        expose_metric("process_cpu_percent", cpu, "CPU percent used by this process")
        mem = proc.memory_percent()
        # - Memory percent
        expose_metric("process_memory_percent", mem, "Memory percent used by this process")
        rss = getattr(proc.memory_info(), "rss", 0)
        # - RSS memory (resident set size)
        expose_metric("process_memory_rss_bytes", rss, "Resident memory used by this process (bytes)")
        uptime = time.time() - proc.create_time()
        # - Process uptime
        expose_metric("process_uptime_seconds", uptime, "Uptime of this process in seconds")
        threads = proc.num_threads()
        # - Number of threads
        expose_metric("process_num_threads", threads, "Number of threads in this process")
        # - Number of open file descriptors (if available on the platform)
        # Use getattr to avoid static analysis/linter errors
        num_fds_fn = getattr(proc, "num_fds", None)
        if callable(num_fds_fn):
            try:
                fds = num_fds_fn()
                # Only expose the metric if fds is an int
                if isinstance(fds, int):
                    expose_metric("process_num_fds", float(fds), "Number of open file descriptors")
            except Exception as exc:
                # May occur on platforms without num_fds support; ignore silently
                logger.debug("Failed to obtain number of file descriptors: %s", exc, exc_info=True)
    except Exception as exc:
        logger.debug("Failed to expose process metrics: %s", exc, exc_info=True)


def get_metrics_bytes() -> bytes:
    """Return Prometheus exposition bytes for current metrics.

    - If `prometheus_client` is available, return `generate_latest()` output.
    - Otherwise, build a text exposition from the latest JSONL and a few
      lightweight process/load metrics.
    """
    if _HAVE_PROM:
        try:
            from prometheus_client import generate_latest  # type: ignore

            return generate_latest()
        except Exception:
            logger.debug("prometheus_client present but failed to generate latest", exc_info=True)

    # Fallback: build a simple text exposition from JSONL and psutil
    lines = []
    try:
        jsonl_path = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "json")
        files = [f for f in os.listdir(jsonl_path) if f.startswith("monitoring-") and f.endswith(".jsonl")]
        if files:
            files.sort(reverse=True)
            latest_file = os.path.join(jsonl_path, files[0])
            with open(latest_file, "rb") as f:
                f.seek(0, os.SEEK_END)
                pos = f.tell()
                line = b""
                while pos > 0:
                    pos -= 1
                    f.seek(pos)
                    char = f.read(1)
                    if char == b"\n" and line:
                        break
                    line = char + line
                last_json = line.decode("utf-8").strip()
            if last_json:
                import json as _json

                try:
                    metrics = _json.loads(last_json)
                except Exception:
                    metrics = {}
                # If metrics contains a 'metrics' sub-dict, use it
                items: Iterable[Tuple[str, Any]] = ()
                if isinstance(metrics, dict):
                    m = metrics.get("metrics") if "metrics" in metrics else metrics
                    if isinstance(m, dict):
                        items = m.items()
                for k, v in items:
                    if isinstance(v, bool):
                        out = "1" if v else "0"
                    elif isinstance(v, (int, float)):
                        out = str(v)
                    else:
                        try:
                            out = str(float(v))
                        except (ValueError, TypeError):
                            continue
                    lines.append(f"monitoring_{k} {out}")
    except Exception as exc:
        logger.debug("Failed to build metrics from JSONL: %s", exc, exc_info=True)

    # Add process-level metrics
    try:
        proc = psutil.Process()
        cpu = proc.cpu_percent(interval=0.0)
        lines.append(f"process_cpu_percent {cpu}")
        mem = proc.memory_percent()
        lines.append(f"process_memory_percent {mem}")
        rss = getattr(proc.memory_info(), "rss", 0)
        lines.append(f"process_memory_rss_bytes {rss}")
        uptime = time.time() - proc.create_time()
        lines.append(f"process_uptime_seconds {uptime}")
        threads = proc.num_threads()
        lines.append(f"process_num_threads {threads}")
    except Exception:
        logger.debug("Failed to collect process metrics", exc_info=True)

    # Load averages
    try:
        if hasattr(os, "getloadavg"):
            l1, l5, l15 = os.getloadavg()
            lines.append(f"monitoring_load_1 {float(l1)}")
            lines.append(f"monitoring_load_5 {float(l5)}")
            lines.append(f"monitoring_load_15 {float(l15)}")
    except OSError:
        pass

    return "\n".join(lines).encode("utf-8")
