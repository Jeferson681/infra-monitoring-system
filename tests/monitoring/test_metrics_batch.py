from types import SimpleNamespace

from src.monitoring import metrics


def test_safe_float_and_counter():
    """Teste para validação das funções _safe_float e _safe_counter."""
    assert metrics._safe_float("3.14") == 3.14
    assert metrics._safe_float(5) == 5.0
    assert metrics._safe_float("nan") is None
    assert metrics._safe_float(float("inf")) is None
    assert metrics._safe_float(object()) is None

    assert metrics._safe_counter(10) == 10
    assert metrics._safe_counter("7") == 7
    assert metrics._safe_counter(-1) is None
    assert metrics._safe_counter("notint") is None


def test_parse_first_float_from_text():
    """Teste para extração do primeiro float de uma string."""
    assert metrics._parse_first_float_from_text("temp=42.5 C") == 42.5
    assert metrics._parse_first_float_from_text("no numbers here") is None
    assert metrics._parse_first_float_from_text("  -1.23 something") == -1.23


def test_get_temp_from_script_success_and_failure(monkeypatch):
    """Teste para obtenção de temperatura via script, cobrindo sucesso e falha."""

    class FakeProc:
        def __init__(self, out):
            self.stdout = out

    def fake_run_ok(cmd, capture_output, text, timeout):
        return FakeProc("42.5\n")

    def fake_run_err(cmd, capture_output, text, timeout):
        raise metrics.subprocess.SubprocessError("fail")

    monkeypatch.setattr(metrics.subprocess, "run", fake_run_ok)
    # using Path to a fake script is fine; function only uses subprocess
    assert metrics._get_temp_from_script(metrics.Path("fake")) == 42.5

    monkeypatch.setattr(metrics.subprocess, "run", fake_run_err)
    assert metrics._get_temp_from_script(metrics.Path("fake")) is None


def test_temperature_collector_posix_and_nonposix(monkeypatch, tmp_path):
    """Teste para coleta de temperatura em ambientes POSIX e não-POSIX."""
    # Non-posix should return None
    monkeypatch.setattr(metrics.os, "name", "nt")
    assert metrics._temperature_collector() is None

    # Posix path exists and executable -> delegate to _get_temp_from_script
    monkeypatch.setattr(metrics.os, "name", "posix")

    # Create a FakePath class to avoid instantiating PosixPath on Windows
    class FakePath:
        def __init__(self, p):
            self._p = p

        def resolve(self):
            return self

        @property
        def parents(self):
            # allow indexing parents[2]
            return [self, self, self]

        def __truediv__(self, other):
            return self

        def exists(self):
            return True

        def __fspath__(self):
            return str(self._p)

    monkeypatch.setattr(metrics, "Path", FakePath)
    monkeypatch.setattr(metrics.os, "access", lambda p, m: True)
    monkeypatch.setattr(metrics, "_get_temp_from_script", lambda p: 30.0)
    assert metrics._temperature_collector() == 30.0


def test_get_network_latency_ping_and_tcp(monkeypatch):
    """Teste para obtenção de latência de rede via ping e fallback TCP."""

    # ping success path
    def fake_check_output(cmd, stderr, text, timeout):
        return "64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=12.34 ms"

    monkeypatch.setattr(metrics.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(metrics, "_last_latency_estimated", False)
    v = metrics.get_network_latency("8.8.8.8", 53, timeout=1.0)
    assert isinstance(v, float) and v == 12.34

    # ping fails -> tcp fallback; simulate perf_counter progression
    def fake_check_output_err(cmd, stderr, text, timeout):
        raise metrics.subprocess.SubprocessError()

    seq = iter([1.0, 1.01])

    def fake_perf_counter():
        return next(seq)

    class DummyConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(metrics.subprocess, "check_output", fake_check_output_err)
    monkeypatch.setattr(metrics.time, "perf_counter", fake_perf_counter)
    monkeypatch.setattr(metrics.socket, "create_connection", lambda *a, **k: DummyConn())
    v2 = metrics.get_network_latency("8.8.8.8", 53, timeout=1.0)
    # should be small but > 0 (millisecond rounding)
    assert isinstance(v2, float) and v2 >= 0.0


def test_get_disk_percent_and_usage(monkeypatch):
    """Teste para obtenção do uso de disco e tratamento de falhas."""
    # success path for disk percent
    monkeypatch.setattr(metrics.psutil, "disk_usage", lambda p: SimpleNamespace(percent=42))
    assert metrics.get_disk_percent(None) == 42

    # failure path: disk_usage raises OSError for candidates -> None
    def raise_oserror(p):
        raise OSError()

    monkeypatch.setattr(metrics.psutil, "disk_usage", raise_oserror)
    monkeypatch.setattr(metrics, "_disk_candidate_paths", lambda: [metrics.Path("/nonexist")])
    assert metrics.get_disk_percent(None) is None


def test_get_memory_and_disk_info(monkeypatch):
    """Teste para obtenção de informações de memória e disco."""
    monkeypatch.setattr(metrics.psutil, "virtual_memory", lambda: SimpleNamespace(used=1000, total=2000))
    assert metrics.get_memory_info() == (1000, 2000)

    monkeypatch.setattr(metrics.psutil, "disk_usage", lambda p: SimpleNamespace(used=300, total=1000))
    used, total = metrics.get_disk_usage_info(None)
    assert used == 300 and total == 1000
