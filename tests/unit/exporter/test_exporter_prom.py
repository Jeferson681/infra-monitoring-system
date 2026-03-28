from types import ModuleType

import pytest


def test_sanitize_metric_name_and_expose_with_prom(monkeypatch):
    """When prometheus_client is available, exporter creates gauges and starts server."""
    # Create a fake prometheus_client with Gauge and start_http_server
    fake_mod = ModuleType("prometheus_client")

    class FakeGauge:
        def __init__(self, name, desc):
            self.name = name
            self.desc = desc
            self.value = None

        def set(self, v):
            self.value = v

    def fake_start_http_server(port, addr):
        fake_mod.started = addr, port

    fake_mod.Gauge = FakeGauge
    fake_mod.start_http_server = fake_start_http_server
    # allow recording start
    fake_mod.started = None

    # Patch the exporter module's import mechanism by injecting into sys.modules
    import sys

    sys.modules["prometheus_client"] = fake_mod

    # Now reload the canonical exporter package to pick up the fake
    import importlib

    exp = importlib.reload(
        importlib.import_module("infra_monitoring.api.exporter.prometheus")
    )

    # test sanitize
    san = exp._sanitize_metric_name("1bad-name%!*")
    assert san[0] == "_"
    # start exporter should not raise; HTTP server is provided by main_http
    exp.start_exporter(port=9001, addr="127.0.0.1")
    # Prometheus exporter now only initializes metrics; it must NOT call start_http_server
    assert fake_mod.started is None

    # expose metric should create and set a gauge with the sanitized name and value
    exp.expose_metric("my.metric-name", 3.14)
    assert exp._gauges, "_gauges should not be empty after expose_metric"
    found = False
    for g in exp._gauges.values():
        name = getattr(g, "name", "")
        if name.startswith("my_metric_name") or name == "my_metric_name":
            found = True
            # verify the stored value on the gauge if available
            val = getattr(g, "value", None)
            if val is None:
                # fallback: some fake gauge implementations store _value
                val = getattr(getattr(g, "_value", {}), "get", lambda: None)()
            assert isinstance(val, (int, float))
            assert float(val) == pytest.approx(3.14)
    assert found, "sanitized gauge name not found in _gauges"


def test_expose_metric_without_prom(monkeypatch):
    """When prometheus_client is absent, expose_metric is a no-op."""
    # Simula ausência de prometheus_client forçando ImportError
    import builtins

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "prometheus_client":
            raise ImportError("No module named 'prometheus_client'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    import importlib

    exp = importlib.reload(
        importlib.import_module("infra_monitoring.api.exporter.prometheus")
    )
    if hasattr(exp, "_gauges"):
        exp._gauges.clear()
    # Should be no-op and not raise
    exp.expose_metric("abc", 1.0)
    # _gauges should permanecer vazio
    assert exp._gauges == {}
