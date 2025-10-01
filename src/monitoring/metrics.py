"""Coleta métricas do sistema.

Coleta CPU, RAM, Disco, Ping, Latência, Rede e Temperatura. Este módulo
prefere operações em Python puro e seguras. Quando possível evita chamar
programas externos para reduzir riscos de injeção.
"""

from __future__ import annotations

import time

import psutil

from system.helpers import validate_host_port


def collect_metrics() -> dict[str, float | None]:
    """Collect and normalize all system metrics.

    Returns a mapping of metric name -> value where missing/unavailable
    numeric metrics are represented as None.
    """
    metrics: dict[str, float | None] = {}
    metrics["cpu_percent"] = max(0.0, min(100.0, get_cpu_percent()))
    metrics["memory_percent"] = max(0.0, min(100.0, get_memory_percent()))
    metrics["disk_percent"] = max(0.0, min(100.0, get_disk_percent()))

    net = get_network_stats()
    metrics["bytes_sent"] = float(net.get("bytes_sent", 0))
    metrics["bytes_recv"] = float(net.get("bytes_recv", 0))

    ping = get_ping()
    metrics["ping_ms"] = ping if ping >= 0.0 else None

    latency = get_latency()
    metrics["latency_ms"] = latency if latency >= 0.0 else None

    return metrics


def get_cpu_percent(interval: float = 1.0) -> float:
    """Return CPU usage percentage."""
    return psutil.cpu_percent(interval=interval)


def get_memory_percent() -> float:
    """Return RAM usage percentage."""
    return psutil.virtual_memory().percent


def get_disk_percent(path: str = "/") -> float:
    """Return disk usage percentage for the specified path."""
    return psutil.disk_usage(path).percent


def get_network_stats() -> dict[str, float]:
    """Return network statistics (bytes sent/received)."""
    net = psutil.net_io_counters()
    return {
        "bytes_sent": float(net.bytes_sent),
        "bytes_recv": float(net.bytes_recv),
    }


def _measure_ping(host: str = "8.8.8.8", timeout: int = 1000) -> float:
    """Measure a 'ping' value (ms).

    This implementation prefers a safe TCP connect measurement rather
    than invoking the system `ping` binary. It avoids shell/command
    injection risks and works without elevated privileges.

    The function returns -1.0 on error or when the value is unavailable.
    """
    # Prefer validating the host as an IPv4 address to avoid resolving
    # arbitrary strings that could lead to unexpected subprocess usage.
    if not validate_host_port(host, 53):
        return -1.0

    # Reuse the TCP-based latency measurer on a common port (DNS/53).
    try:
        return _measure_latency(host, port=53, timeout=timeout / 1000.0)
    except Exception:
        import logging

        logging.exception("Error collecting ping (tcp fallback)")
        return -1.0


def _measure_latency(host: str = "8.8.8.8", port: int = 80, timeout: float = 2.0) -> float:
    """Measure TCP latency (ms)."""
    import socket

    if not validate_host_port(host, port):
        return -1.0
    start = time.time()
    try:
        sock = socket.create_connection((host, port), timeout)
        sock.close()
        end = time.time()
        return (end - start) * 1000.0
    except Exception:
        import logging

        logging.exception("Error collecting latency")
        return -1.0


def get_ping(host: str = "8.8.8.8", timeout: int = 1000) -> float:
    """Return ping response time (ms)."""
    return _measure_ping(host, timeout)


def get_latency(
    host: str = "8.8.8.8",
    port: int = 80,
    timeout: float = 2.0,
) -> float:
    """Return TCP latency (ms)."""
    return _measure_latency(host, port, timeout)
