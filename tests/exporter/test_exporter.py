import importlib
import sys
from types import SimpleNamespace

import pytest


def test_import_exporter():
    """Importa o exporter sem erros."""
    import src.exporter.prometheus as prometheus

    assert prometheus is not None


def test_sanitize_metric_name_basic():
    """Sanitize: mantém nomes válidos e substitui caracteres inválidos."""
    from src.exporter.prometheus import _sanitize_metric_name

    assert _sanitize_metric_name("monitoring_cpu_percent") == "monitoring_cpu_percent"
    assert _sanitize_metric_name("1bad-start") == "_bad_start"
    assert _sanitize_metric_name("weird.chars/and:spaces") == "weird_chars_and:spaces"


def test_expose_metric_no_prom(monkeypatch, caplog):
    """Quando prometheus_client estiver ausente, expose_metric não levanta e loga."""
    # Ensure prometheus_client is absent
    monkeypatch.setitem(sys.modules, "prometheus_client", None)
    # reload module to pick up absence
    mod = importlib.reload(importlib.import_module("src.exporter.exporter"))
    import logging

    caplog.clear()
    caplog.set_level(logging.DEBUG)

    # calling expose_metric with prometheus missing should log debug and not raise
    mod.expose_metric("monitoring_cpu_percent", 12.3)
    assert any("prometheus_client not available" in r.message for r in caplog.records)


def test_expose_metric_with_prom(monkeypatch):
    """Com um cliente prometheus simulado, expose_metric cria Gauge e atualiza valor."""
    # Create a fake Gauge type with set method and track calls
    calls = {}

    class FakeGauge:
        def __init__(self, name, desc):
            self.name = name
            self.desc = desc

        def set(self, v):
            calls[self.name] = float(v)

    fake = SimpleNamespace(Gauge=FakeGauge, start_http_server=lambda *a, **k: None)
    monkeypatch.setitem(sys.modules, "prometheus_client", fake)

    # reload module to pick up fake prometheus_client
    mod = importlib.reload(importlib.import_module("src.exporter.exporter"))

    mod.expose_metric("monitoring_cpu_percent", 5.5)
    # sanitized name should be present in calls
    assert "monitoring_cpu_percent" in calls
    assert calls["monitoring_cpu_percent"] == pytest.approx(5.5)


def test_start_exporter_invokes_start_http_server(monkeypatch):
    """start_exporter deve chamar start_http_server com porta/addr do env."""
    events = {}

    def fake_start_http_server(port, addr):
        events["started"] = (addr, int(port))

    fake = SimpleNamespace(Gauge=lambda *a, **k: None, start_http_server=fake_start_http_server)
    monkeypatch.setitem(sys.modules, "prometheus_client", fake)

    mod = importlib.reload(importlib.import_module("src.exporter.exporter"))
    # set env to provide port
    monkeypatch.setenv("MONITORING_EXPORTER_PORT", "9009")

    mod.start_exporter()
    assert events.get("started") == ("127.0.0.1", 9009)
