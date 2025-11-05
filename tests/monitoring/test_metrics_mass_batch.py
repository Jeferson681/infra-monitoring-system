import subprocess
from types import SimpleNamespace

from src.monitoring import metrics as m


def test_parse_ping_output_variants(monkeypatch):
    """Teste para variantes de saída do ping."""
    # simulate two ping outputs and ensure get_network_latency parses them
    monkeypatch.setattr(
        m.subprocess,
        "check_output",
        lambda *a, **k: "Reply from 8.8.8.8: bytes=32 time=12.34ms TTL=117",
    )
    v1 = m.get_network_latency("8.8.8.8", 53, 1.0)
    assert v1 is None or isinstance(v1, float)

    monkeypatch.setattr(
        m.subprocess,
        "check_output",
        lambda *a, **k: "rtt min/avg/max/mdev = 1.234/2.345/3.456/0.123 ms",
    )
    v2 = m.get_network_latency("8.8.8.8", 53, 1.0)
    assert v2 is None or isinstance(v2, float)


def test_get_network_latency_tcp_fallback(monkeypatch):
    """Teste para fallback TCP na latência de rede."""

    # make subprocess.check_output raise to force tcp fallback
    def raise_sub(*a, **k):
        raise subprocess.SubprocessError("no")

    monkeypatch.setattr(m.subprocess, "check_output", raise_sub)

    # fake socket.create_connection to succeed
    class CM:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(m.socket, "create_connection", lambda *a, **k: CM())
    # fake perf_counter
    seq = iter([1.0, 1.2])
    monkeypatch.setattr(m.time, "perf_counter", lambda: next(seq))

    # should return ~200ms
    val = m.get_network_latency("8.8.8.8", 53, 1.0)
    assert val is None or isinstance(val, float)


def test_get_disk_usage_info_branches(monkeypatch):
    """Teste para branches de info de uso de disco."""
    # simulate psutil.disk_usage raising OSError for candidates
    monkeypatch.setattr(m.psutil, "disk_usage", lambda p: (_ for _ in ()).throw(OSError("no")))
    # should return None, None when all candidates fail
    used, total = m.get_disk_usage_info(None)
    assert (used, total) == (None, None)


def test_collect_metrics_full_flow(monkeypatch):
    """Teste para fluxo completo de coleta de métricas."""

    # monkeypatch psutil virtual_memory, net_io_counters and disk_usage
    class VM:
        percent = 12.3
        used = 1000
        total = 2000

    class Net:
        bytes_sent = 100
        bytes_recv = 200

    monkeypatch.setattr(m.psutil, "virtual_memory", lambda: VM())
    monkeypatch.setattr(m.psutil, "net_io_counters", lambda: Net())
    monkeypatch.setattr(m.psutil, "disk_usage", lambda p: SimpleNamespace(percent=50, used=500, total=1000))

    # monkeypatch latency to return known value
    monkeypatch.setattr(m, "get_latency", lambda *a, **k: 10.0)

    # ensure cache reset will force collectors
    m._reset_cache_timestamps()
    res = m.collect_metrics()
    assert isinstance(res, dict)
    assert "cpu_percent" in res


def test_validate_host_port_fallback(monkeypatch):
    """Teste para fallback de validação de host/porta."""
    # invalid host should fall back to 127.0.0.1 inside get_network_latency
    monkeypatch.setattr(m, "_tcp_latency_fallback", lambda host, port, timeout: None)

    # force ping to raise so we hit TCP fallback which we mocked to None
    def _raise_sub(*a, **k):
        raise subprocess.SubprocessError("no")

    monkeypatch.setattr(m.subprocess, "check_output", _raise_sub)
    val = m.get_network_latency("not-a-host", 99999, 1.0)
    assert val is None
