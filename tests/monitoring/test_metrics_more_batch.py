from types import SimpleNamespace
from pathlib import Path

import pytest

from src.monitoring import metrics as m


def test_parse_first_float_from_text():
    """Testa extração do primeiro float de texto."""
    assert m._parse_first_float_from_text("temp= 12.34 C") == pytest.approx(12.34)
    assert m._parse_first_float_from_text("no numbers here") is None
    assert m._parse_first_float_from_text("") is None
    assert m._parse_first_float_from_text("-3.5 degrees") == pytest.approx(-3.5)


def test_safe_float_and_counter():
    """Testa _safe_float e _safe_counter para valores válidos e nulos."""
    assert m._safe_float("1.23") == pytest.approx(1.23)
    assert m._safe_float("nan") is None
    assert m._safe_float(object()) is None

    assert m._safe_counter(123) == 123
    assert m._safe_counter("10") == 10
    assert m._safe_counter(-1) is None
    assert m._safe_counter(object()) is None


def test_get_network_stats_and_disk_percent(monkeypatch):
    """Testa get_network_stats e get_disk_percent com mocks."""
    # fake net io counters
    fake_net = SimpleNamespace(bytes_sent=1000, bytes_recv=2000)

    monkeypatch.setattr(m.psutil, "net_io_counters", lambda: fake_net)
    ns = m.get_network_stats()
    assert ns["bytes_sent"] == 1000
    assert ns["bytes_recv"] == 2000

    # disk percent: monkeypatch disk candidate paths and psutil.disk_usage
    monkeypatch.setattr(m, "_disk_candidate_paths", lambda: [Path("/nonexistent"), Path("/also")])

    class DU:
        def __init__(self, percent):
            self.percent = percent

    # First call raises OSError, second returns value
    calls = {"n": 0}

    def fake_disk_usage(p):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("no access")
        return DU(42.5)

    monkeypatch.setattr(m.psutil, "disk_usage", fake_disk_usage)
    pct = m.get_disk_percent()
    assert pct == pytest.approx(42.5)


def test_get_disk_percent_with_path(monkeypatch, tmp_path):
    """Testa get_disk_percent com caminho específico."""

    class DU:
        def __init__(self, percent):
            self.percent = percent

    monkeypatch.setattr(m.psutil, "disk_usage", lambda p: DU(7.0))
    assert m.get_disk_percent(str(tmp_path)) == pytest.approx(7.0)


def test_get_network_latency_ping_success(monkeypatch):
    """Testa get_network_latency com sucesso via ping."""
    # simulate ping output
    monkeypatch.setattr(m.subprocess, "check_output", lambda *a, **k: "round-trip min/avg/max = 12.34 ms")
    # ensure tcp fallback not called by forcing socket.create_connection to raise if used
    monkeypatch.setattr(m.socket, "create_connection", lambda *a, **k: (_ for _ in ()).throw(OSError("no")))

    # reset flag
    m._last_latency_estimated = False
    v = m.get_network_latency("8.8.8.8", 53, 1.0)
    assert v == pytest.approx(12.34)
    assert m._last_latency_estimated is False


def test_get_network_latency_ping_fallback_tcp(monkeypatch):
    """Testa fallback TCP para get_network_latency quando ping falha."""

    # make check_output raise to trigger fallback
    def raise_sub(*a, **k):
        raise m.subprocess.SubprocessError("ping missing")

    monkeypatch.setattr(m.subprocess, "check_output", raise_sub)

    # fake socket.create_connection as context manager
    class CM:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(m.socket, "create_connection", lambda *a, **k: CM())

    # make perf_counter return two different times
    seq = iter([1.0, 1.123])
    monkeypatch.setattr(m.time, "perf_counter", lambda: next(seq))

    m._last_latency_estimated = False
    v = m.get_network_latency("8.8.8.8", 53, 1.0)
    assert v == pytest.approx(round((1.123 - 1.0) * 1000, 2))
    assert m._last_latency_estimated is True


def test_get_cpu_percent_warmup(monkeypatch):
    """Testa get_cpu_percent com caminho de aquecimento."""
    # simulate psutil.cpu_percent first 0.0 then 5.0
    calls = {"n": 0}

    def fake_cpu_percent(interval=0.0):
        calls["n"] += 1
        if calls["n"] == 1:
            return 0.0
        return 5.0

    monkeypatch.setattr(m.psutil, "cpu_percent", fake_cpu_percent)
    # reset module global
    m._cpu_warmed_up = False
    v = m.get_cpu_percent()
    # warmed-up path should perform a second sample and return 5.0
    assert v == pytest.approx(5.0)


def test_get_cpu_freq_ghz(monkeypatch):
    """Testa get_cpu_freq_ghz para valores válidos e nulos."""

    class F:
        def __init__(self, current):
            self.current = current

    monkeypatch.setattr(m.psutil, "cpu_freq", lambda: F(2300))
    assert m.get_cpu_freq_ghz() == pytest.approx(2.3)

    monkeypatch.setattr(m.psutil, "cpu_freq", lambda: None)
    assert m.get_cpu_freq_ghz() is None


def test_get_temp_from_script_and_collector(monkeypatch, tmp_path):
    """Testa _get_temp_from_script e o coletor de temperatura."""
    # simulate subprocess.run returning specific stdout
    fake_proc = SimpleNamespace(stdout="Temp= 45.6 C\n", returncode=0)
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: fake_proc)
    script = tmp_path / "temp.sh"
    script.write_text("echo 45.6")
    val = m._get_temp_from_script(script)
    assert val == pytest.approx(45.6)

    # temperature collector should return None on non-posix
    monkeypatch.setattr(m.os, "name", "nt", raising=False)
    assert m._temperature_collector() is None
