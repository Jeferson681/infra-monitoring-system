import subprocess
import socket

from src.monitoring import metrics as m


def test_safe_float_and_counter():
    """Teste para funções de float seguro e contador."""
    assert m._safe_float("1.23") == 1.23
    assert m._safe_float("nan") is None
    assert m._safe_float(object()) is None
    assert m._safe_counter("5") == 5
    assert m._safe_counter(-1) is None


def test_parse_first_float_from_text():
    """Teste para extração do primeiro float de texto."""
    assert m._parse_first_float_from_text("value= 12.34 ms") == 12.34
    assert m._parse_first_float_from_text("no number") is None


def test_tcp_latency_fallback_socket_error(monkeypatch):
    """Teste para fallback TCP com erro de socket."""
    # simulate create_connection raising
    monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: (_ for _ in ()).throw(OSError("no")))
    assert m._tcp_latency_fallback("8.8.8.8", 53, 0.01) is None


def test_network_latency_ping_fallback(monkeypatch):
    """Teste para fallback de latência de rede via ping."""
    # simulate subprocess.check_output throwing so we go to TCP fallback
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **kw: (_ for _ in ()).throw(OSError("no ping")))
    # patch tcp fallback to return a known value
    monkeypatch.setattr(m, "_tcp_latency_fallback", lambda h, p, t: 12.34)
    val = m.get_network_latency("8.8.8.8", 53, 0.01)
    assert val == 12.34


def test_cache_get_or_refresh_unknown_collector_failure(monkeypatch):
    """Teste para falha de coletor desconhecido ao atualizar cache."""

    def bad():
        raise OSError("boom")

    # unknown key should call collector directly and return None on failure
    assert m._cache_get_or_refresh("unknown_key", bad) is None


def test_is_stale_and_reset_cache_timestamps():
    """Teste para verificação de stale e reset de timestamps do cache."""
    # set cache ts to old then reset
    m._CACHE["cpu_percent"]["ts"] = 0.0
    assert m._is_stale("cpu_percent") is True
    m._CACHE["cpu_percent"]["ts"] = m._now()
    assert m._is_stale("cpu_percent") is False
    m._reset_cache_timestamps()
    assert m._CACHE["cpu_percent"]["ts"] == 0.0
