from types import ModuleType


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
        setattr(fake_mod, "started", (addr, port))

    setattr(fake_mod, "Gauge", FakeGauge)
    setattr(fake_mod, "start_http_server", fake_start_http_server)
    # allow recording start
    setattr(fake_mod, "started", None)

    # Patch the exporter module's import mechanism by injecting into sys.modules
    import sys

    sys.modules["prometheus_client"] = fake_mod

    # Now reload the canonical exporter package to pick up the fake
    import importlib

    exp = importlib.reload(importlib.import_module("src.exporter.prometheus"))

    # test sanitize
    san = exp._sanitize_metric_name("1bad-name%!*")
    assert san[0] == "_"

    # start exporter should not raise; HTTP server is provided by main_http
    exp.start_exporter(port=9001, addr="127.0.0.1")
    # Prometheus exporter now only initializes metrics; it must NOT call start_http_server
    assert fake_mod.started is None

    # expose metric should create and set a gauge
    exp.expose_metric("my.metric-name", 3.14)
    # gauge stored under sanitized name
    assert any(g.name.startswith("my_metric_name") or g.name == "my_metric_name" for g in exp._gauges.values())


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

    exp = importlib.reload(importlib.import_module("src.exporter.prometheus"))
    if hasattr(exp, "_gauges"):
        exp._gauges.clear()

    # Should be no-op and not raise
    exp.expose_metric("abc", 1.0)
    # _gauges should permanecer vazio
    assert exp._gauges == {}
