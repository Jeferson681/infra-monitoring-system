"""HTTP entrypoint exposing /health and /metrics endpoints.

Provides a small HTTP server used as an optional fallback for Prometheus
scraping and health checks. The server exposes lightweight process and
system metrics and delegates Prometheus exposition to the exporter
subsystem when available.
"""

import json
import os
import psutil
import time  # Needed for uptime
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from src.exporter.promtail import send_log_to_loki


# Default path to the system metrics JSONL directory
SYSTEM_METRICS_JSONL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "json")

try:

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for /health and (optionally) /metrics endpoints."""

    def do_GET(self):
        """Handle GET requests for /health, /metrics and other endpoints."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            system_metrics = self._get_last_system_metrics()
            process_metrics = self._get_process_metrics(prefix="process_")
            status = {
                "status": "ok",
                "system": system_metrics,
                "process": process_metrics,
            }
            self.wfile.write(json.dumps(status).encode("utf-8"))
        elif self.path == "/metrics":
            try:
                from src.exporter.prometheus import get_metrics_bytes

                payload = get_metrics_bytes()
                self.send_response(200)
                self.send_header("Content-type", "text/plain; version=0.0.4; charset=utf-8")
                self.end_headers()
                self.wfile.write(payload)
            except Exception:
                # If metrics generation fails, return 503 so scrapers know to retry later
                import logging

                logging.getLogger(__name__).exception("Failed to generate /metrics")
                self.send_response(503)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def _get_last_system_metrics(self):
        """Read the last line from the system metrics JSONL file."""
        jsonl_path = SYSTEM_METRICS_JSONL_PATH
        system_metrics = {}
        last_json = None
        try:
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
                system_metrics = json.loads(last_json)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).exception("Failed to read metrics from JSONL: %s", exc)
        return system_metrics

    def _get_process_metrics(self, prefix="", prometheus=False):
        """Collect process metrics in real time."""
        proc = psutil.Process()
        metrics = {
            f"{prefix}cpu_percent": proc.cpu_percent(interval=0.0),
            f"{prefix}memory_percent": proc.memory_percent(),
            f"{prefix}memory_rss_bytes": getattr(proc.memory_info(), "rss", 0),
            f"{prefix}uptime_seconds": float(max(0, (time.time() - proc.create_time()))),
            f"{prefix}num_threads": proc.num_threads(),
        }
        num_fds_fn = getattr(proc, "num_fds", None)
        if callable(num_fds_fn):
            try:
                fds = num_fds_fn()
                if isinstance(fds, int):
                    metrics[f"{prefix}num_fds"] = fds
            except Exception as exc:
                import logging

                logging.getLogger(__name__).debug("Failed to obtain number of file descriptors: %s", exc, exc_info=True)
        # Adjust names for Prometheus if needed
        if prometheus:
            # Remove duplicated prefix for Prometheus
            metrics = {k.replace("process_process_", "process_"): v for k, v in metrics.items()}
        return metrics

    def _format_prometheus_metrics(self, system_metrics, process_metrics):
        """Format metrics for Prometheus exposition format."""
        lines = []
        # System metrics
        if "metrics" in system_metrics and isinstance(system_metrics["metrics"], dict):
            items = system_metrics["metrics"].items()
        else:
            items = system_metrics.items()

        for k, v in items:
            out = self._value_to_prometheus(v)
            if out is not None:
                lines.append(f"monitoring_{k} {out}")
        # Process metrics
        for k, v in process_metrics.items():
            out = self._value_to_prometheus(v)
            if out is not None:
                lines.append(f"{k} {out}")

        # Additional lightweight metrics: load averages, CPU temperature and network rates
        # Load averages (0 when unavailable)
        load_vals = self._get_load_averages()
        if load_vals is not None:
            l1, l5, l15 = load_vals
        else:
            l1 = l5 = l15 = 0.0
        lines.append(f"monitoring_load_1 {self._value_to_prometheus(l1)}")
        lines.append(f"monitoring_load_5 {self._value_to_prometheus(l5)}")
        lines.append(f"monitoring_load_15 {self._value_to_prometheus(l15)}")

        # CPU temperature (if available)
        cpu_temp = self._get_cpu_temp_c(system_metrics)
        if cpu_temp is None:
            # use -1 when unavailable
            cpu_temp = -1.0
        lines.append(f"monitoring_cpu_temp_c {self._value_to_prometheus(cpu_temp)}")

        # Network rates (Mbps)
        net_in, net_out = self._get_network_rates()
        # export 0.0 when network rates are not yet available
        if net_in is None:
            net_in = 0.0
        if net_out is None:
            net_out = 0.0
        lines.append(f"monitoring_net_in_mbps {self._value_to_prometheus(net_in)}")
        lines.append(f"monitoring_net_out_mbps {self._value_to_prometheus(net_out)}")
        return "\n".join(lines).encode("utf-8")

    # Helpers
    def _get_load_averages(self):
        """Return (1,5,15) load averages if supported, else None."""
        try:
            if hasattr(os, "getloadavg"):
                vals = os.getloadavg()
                return float(vals[0]), float(vals[1]), float(vals[2])
        except Exception as exc:
            import logging

            logging.getLogger(__name__).debug("Failed to obtain load averages: %s", exc)
        return None

    def _get_cpu_temp_c(self, system_metrics):
        """Try to obtain CPU temperature.

        Prefer `psutil.sensors_temperatures()` when available. If that fails,
        fall back to `system_metrics['metrics']['temperature']` from JSONL.
        Returns Celsius as float, or `None` if unavailable.
        """
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    # pick first available sensor temperature
                    for key, entries in temps.items():
                        if entries:
                            t = entries[0].current
                            if t is not None:
                                return float(t)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).debug("Failed to obtain temperature via psutil: %s", exc)
        # fallback to system metrics JSONL
        try:
            if isinstance(system_metrics, dict):
                m = system_metrics.get("metrics") if "metrics" in system_metrics else system_metrics
                if isinstance(m, dict):
                    temp = m.get("temperature_celsius") if isinstance(m, dict) else None
                    # fallback to legacy key for backward compatibility
                    if temp is None:
                        temp = m.get("temperature")
                    if temp is not None:
                        return float(temp)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).debug("Failed to read temperature from JSONL: %s", exc)
        return None

    # Module-level state for computing network deltas
    _last_net = None
    _last_net_ts = None

    def _get_network_rates(self):
        """Compute network in/out rates (Mbps) using psutil.net_io_counters().

        Returns a tuple `(in_mbps, out_mbps)` or `(None, None)` on error.
        """
        try:
            counters = psutil.net_io_counters()
            now = time.time()
            total_bytes_sent = getattr(counters, "bytes_sent", None)
            total_bytes_recv = getattr(counters, "bytes_recv", None)
            if total_bytes_sent is None or total_bytes_recv is None:
                return None, None

            last = self.__class__._last_net
            last_ts = self.__class__._last_net_ts
            # initialize if missing
            if last is None or last_ts is None:
                self.__class__._last_net = (total_bytes_recv, total_bytes_sent)
                self.__class__._last_net_ts = now
                return None, None

            prev_recv, prev_sent = last
            dt = now - last_ts
            if dt <= 0:
                return None, None

            delta_recv = max(0, total_bytes_recv - prev_recv)
            delta_sent = max(0, total_bytes_sent - prev_sent)
            # bytes/sec -> megabits per second
            in_mbps = (delta_recv / dt) * 8 / 1_000_000
            out_mbps = (delta_sent / dt) * 8 / 1_000_000

            # update stored counters
            self.__class__._last_net = (total_bytes_recv, total_bytes_sent)
            self.__class__._last_net_ts = now

            return float(in_mbps), float(out_mbps)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).debug("Error computing network rates: %s", exc)
            return None, None

    def _value_to_prometheus(self, v):
        """Attempt to normalize a value to a numeric literal accepted by Prometheus.

        Returns a string of the number (e.g. '1' or '0' or '3.14') or `None` if not convertible.
        """
        # booleans -> 1/0
        if isinstance(v, bool):
            return "1" if v else "0"
        # numbers
        if isinstance(v, (int, float)):
            return str(v)
        # strings: try to convert to float, or accept 'true'/'false'
        if isinstance(v, str):
            sv = v.strip()
            try:
                fv = float(sv)
                return str(fv)
            except Exception:
                if sv.lower() in ("true", "false"):
                    return "1" if sv.lower() == "true" else "0"
        return None

    def log_message(self, format, *args):
        """Silence HTTP request logs to the console."""
        pass


def run_http_server(addr="127.0.0.1", port=8000):
    """Start the HTTP server to expose metrics."""
    # Ensure module directory exists
    os.makedirs(os.path.dirname(__file__), exist_ok=True)
    try:
        server = HTTPServer((addr, port), HealthHandler)
        print(f"[HTTP] Serving at http://{addr}:{port} (/health, /metrics)")
        server.serve_forever()
    except Exception as e:
        print(f"[HTTP] Error starting server: {e}")


def run_promtail_worker():
    """Send heartbeat logs to Loki every 10 seconds."""
    import logging

    while True:
        msg = f"promtail heartbeat: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        ok = send_log_to_loki(msg)
        if not ok:
            logging.getLogger(__name__).warning("Failed to send heartbeat to Loki")
        time.sleep(10)


if __name__ == "__main__":
    port = int(os.getenv("MONITORING_HTTP_PORT", "8000"))
    # Start Promtail/Loki in a separate thread
    promtail_thread = threading.Thread(target=run_promtail_worker, daemon=True)
    promtail_thread.start()
    # Start HTTP server (Prometheus fallback)
    run_http_server(port=port)


# Silence Vulture: methods used as callbacks by `HTTPServer`.
_VULTURE_KEEP = [HealthHandler.do_GET, HealthHandler.log_message]
