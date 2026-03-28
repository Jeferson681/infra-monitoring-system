import importlib

import pytest

mod = importlib.import_module("infra_monitoring.services.monitoring.metrics")


def test_safe_float_and_counter():
    """Testa _safe_float e _safe_counter para valores válidos e nulos."""
    v = mod._safe_float("1.5")
    assert isinstance(v, float) and v == pytest.approx(1.5)
    assert mod._safe_float(None) is None
    c = mod._safe_counter("10")
    assert isinstance(c, int) and c == 10
    assert mod._safe_counter(None) is None


def test_parse_first_float_from_text():
    """Testa extração do primeiro float de texto."""
    v = mod._parse_first_float_from_text("value=12.3 ms")
    assert isinstance(v, float) and v == pytest.approx(12.3)
    assert mod._parse_first_float_from_text("no numbers") is None


def test_tcp_latency_fallback_socket(monkeypatch):
    """Testa fallback TCP para latência de socket."""

    # simulate socket.create_connection success returning a socket-like object with getpeername()
    class FakeSock:
        def __init__(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def getpeername(self):
            return ("127.0.0.1", 80)

        def close(self):
            pass

    def fake_create(hostport, timeout):
        return FakeSock()

    monkeypatch.setattr("socket.create_connection", fake_create)
    # call fallback; likely returns None but should not raise
    res = mod._tcp_latency_fallback("127.0.0.1", 80, 1.0)
    assert res is None or (isinstance(res, float) and res >= 0.0)
