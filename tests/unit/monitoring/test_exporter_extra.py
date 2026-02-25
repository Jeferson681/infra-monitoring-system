from src.exporter import prometheus


def test_sanitize_metric_name_and_no_prom(monkeypatch):
    """_sanitize_metric_name produces a string and expose/start are no-ops when prom missing."""
    assert prometheus._sanitize_metric_name("1bad.name")

    monkeypatch.setattr(prometheus, "_HAVE_PROM", False)
    prometheus.expose_metric("m", 1.0)
    prometheus.start_exporter(port=0)


def test_expose_metric_with_prom(monkeypatch):
    """When prom client present, expose_metric updates/create gauge via set()."""
    monkeypatch.setattr(prometheus, "_HAVE_PROM", True)

    class FakeG:
        def __init__(self):
            self.value = None

        def set(self, v):
            self.value = v

    # Insert using sanitized metric name to match exporter internal keying
    san = prometheus._sanitize_metric_name("m")
    # Ensure exporter module has a Gauge symbol so cast(Gauge, ...) works
    monkeypatch.setattr(prometheus, "Gauge", FakeG, raising=False)
    monkeypatch.setitem(prometheus._gauges, san, FakeG())
    prometheus.expose_metric("m", 2.0)
    assert getattr(prometheus._gauges[san], "value", None) == 2.0
