import subprocess
import psutil

from src.monitoring import metrics


def test_safe_float_accepts_numbers_and_rejects_nan_inf():
    """_safe_float accepts numeric-like input and rejects NaN/Inf/other types."""
    assert metrics._safe_float(1) == 1.0
    assert metrics._safe_float("2.5") == 2.5
    assert metrics._safe_float(float("nan")) is None
    assert metrics._safe_float(float("inf")) is None
    assert metrics._safe_float(object()) is None


def test_safe_counter_valid_and_invalid():
    """_safe_counter converts numeric-like to non-negative ints or returns None."""
    assert metrics._safe_counter(10) == 10
    assert metrics._safe_counter("20") == 20
    assert metrics._safe_counter(-1) is None
    assert metrics._safe_counter("abc") is None


def test_parse_first_float_from_text():
    """_parse_first_float_from_text extracts the first numeric value or returns None."""
    assert metrics._parse_first_float_from_text("temp=23.5 C") == 23.5
    assert metrics._parse_first_float_from_text("no numbers") is None


def test_get_network_stats_monkeypatch(monkeypatch):
    """get_network_stats returns bytes_sent/bytes_recv as ints using psutil."""

    class FakeNet:
        bytes_sent = 100
        bytes_recv = 200

    monkeypatch.setattr(psutil, "net_io_counters", lambda: FakeNet())
    res = metrics.get_network_stats()
    assert res["bytes_sent"] == 100
    assert res["bytes_recv"] == 200


def test_get_disk_percent_with_candidates(monkeypatch, tmp_path):
    """get_disk_percent iterates candidates and returns percent when available."""
    monkeypatch.setattr(metrics, "_disk_candidate_paths", lambda: [tmp_path])

    class FakeDU:
        percent = 42

    monkeypatch.setattr(psutil, "disk_usage", lambda p: FakeDU())
    assert metrics.get_disk_percent() == 42


def test_get_network_latency_tcp_fallback(monkeypatch):
    """If ping fails, get_network_latency falls back to TCP connect measurement."""

    # Force ping to raise CalledProcessError
    def raise_called(*a, **k):
        raise subprocess.CalledProcessError(1, "ping")

    monkeypatch.setattr(metrics.subprocess, "check_output", raise_called)

    # Now mock socket.create_connection to simulate a fast TCP connect
    class DummySocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_create_connection(addr, timeout=None):
        return DummySocket()

    monkeypatch.setattr(metrics.socket, "create_connection", fake_create_connection)

    # Should return a float (ms) or None but should not raise
    val = metrics.get_network_latency(host="127.0.0.1", port=80, timeout=1.0)
    assert val is None or isinstance(val, float)


def test_tcp_latency_fallback_marks_estimated(monkeypatch):
    """_tcp_latency_fallback sets the _last_latency_estimated flag on errors."""

    def raise_oserror(addr, timeout=None):
        raise OSError("conn failed")

    monkeypatch.setattr(metrics.socket, "create_connection", raise_oserror)
    metrics._last_latency_estimated = False
    res = metrics._tcp_latency_fallback("127.0.0.1", 80, 0.5)
    assert metrics._last_latency_estimated is True
    assert res is None


def test_get_cpu_freq_ghz_handles_none(monkeypatch):
    """get_cpu_freq_ghz returns None when psutil.cpu_freq is None."""
    monkeypatch.setattr(psutil, "cpu_freq", lambda: None)
    assert metrics.get_cpu_freq_ghz() is None


def test_get_memory_info_handles_exceptions(monkeypatch):
    """get_memory_info returns (None, None) when psutil.virtual_memory raises."""
    monkeypatch.setattr(psutil, "virtual_memory", lambda: (_ for _ in ()).throw(RuntimeError("oom")))
    used, total = metrics.get_memory_info()
    assert used is None and total is None
