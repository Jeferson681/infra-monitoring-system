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

    # Now reload the exporter module to pick up the fake
    import importlib

    exp = importlib.reload(importlib.import_module("src.exporter.exporter"))

    # test sanitize
    san = exp._sanitize_metric_name("1bad-name%!*")
    assert san[0] == "_"

    # start exporter should not raise and should call fake_start_http_server
    exp.start_exporter(port=9001, addr="127.0.0.1")
    assert fake_mod.started == ("127.0.0.1", 9001)

    # expose metric should create and set a gauge
    exp.expose_metric("my.metric-name", 3.14)
    # gauge stored under sanitized name
    assert any(g.name.startswith("my_metric_name") or g.name == "my_metric_name" for g in exp._gauges.values())


def test_expose_metric_without_prom(monkeypatch):
    """When prometheus_client is absent, expose_metric is a no-op."""
    # Ensure prometheus_client absent
    import sys

    sys.modules.pop("prometheus_client", None)
    import importlib

    exp = importlib.reload(importlib.import_module("src.exporter.exporter"))

    # Should be no-op and not raise
    exp.expose_metric("abc", 1.0)
    # _gauges should remain empty
    assert exp._gauges == {}
