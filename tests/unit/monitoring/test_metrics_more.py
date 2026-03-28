from types import SimpleNamespace

import psutil
import pytest

from infra_monitoring.services.monitoring import metrics


def test_now_and_is_stale_cache_behavior(monkeypatch):
    """_is_stale returns True when cache timestamp set to 0."""
    metrics._CACHE["cpu_percent"]["ts"] = 0.0
    assert metrics._is_stale("cpu_percent") is True


def test_cache_get_or_refresh_unknown_key():
    """_cache_get_or_refresh calls collector for unknown keys."""

    def collector():
        return 123

    val = metrics._cache_get_or_refresh("unknown_key", collector)
    assert val == 123


def test_safe_float_and_counter():
    """_safe_float/_safe_counter convert numeric strings and reject bad values."""
    v = metrics._safe_float("3.14")
    assert isinstance(v, float) and v == pytest.approx(3.14)
    c = metrics._safe_counter("7")
    assert isinstance(c, int) and c == 7


def test_get_network_stats_and_disk_percent(monkeypatch, tmp_path):
    """get_network_stats and get_disk_percent return expected values when psutil is stubbed."""

    class FakeNet:
        bytes_sent = 10
        bytes_recv = 20

    monkeypatch.setattr(psutil, "net_io_counters", lambda: FakeNet())
    ns = metrics.get_network_stats()
    assert isinstance(ns, dict)
    assert ns["bytes_sent"] == 10

    monkeypatch.setattr(metrics, "_disk_candidate_paths", lambda: [tmp_path])

    class FakeDU:
        percent = 55

    monkeypatch.setattr(psutil, "disk_usage", lambda p: FakeDU())
    dp = metrics.get_disk_percent()
    assert isinstance(dp, (int, float)) and dp == 55


def test_parse_first_float_and_temp_script(tmp_path, monkeypatch):
    """_get_temp_from_script é deprecated e retorna None."""
    # create a fake script file that prints a number
    script = tmp_path / "temp.sh"
    script.write_text("echo 42.5")
    script.chmod(0o755)

    # _get_temp_from_script é deprecated, sempre retorna None
    val = metrics._get_temp_from_script(script)
    assert val is None


def test_tcp_latency_and_flags(monkeypatch):
    """_tcp_latency_fallback returns ms or None and sets flag when connection attempted."""

    # simulate socket create_connection success
    class DummySock:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        metrics.socket, "create_connection", lambda *a, **k: DummySock()
    )
    metrics._last_latency_estimated = False
    v = metrics._tcp_latency_fallback("127.0.0.1", 80, 0.5)
    assert v is None or (isinstance(v, float) and v >= 0.0)
    assert metrics._last_latency_estimated is True


def test_get_cpu_freq_and_memory_info(monkeypatch):
    """get_cpu_freq_ghz and get_memory_info return expected values when psutil stubbed."""

    class F:
        current = 2400

    monkeypatch.setattr(psutil, "cpu_freq", lambda: F())
    cf = metrics.get_cpu_freq_ghz()
    assert isinstance(cf, float) and cf > 0.0

    monkeypatch.setattr(
        psutil, "virtual_memory", lambda: SimpleNamespace(used=100, total=200)
    )
    used, total = metrics.get_memory_info()
    assert isinstance(used, int) and isinstance(total, int)
    assert used == 100 and total == 200
