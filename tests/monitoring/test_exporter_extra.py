from src.exporter import exporter


def test_sanitize_metric_name_and_no_prom(monkeypatch):
    """_sanitize_metric_name produces a string and expose/start are no-ops when prom missing."""
    assert exporter._sanitize_metric_name("1bad.name")

    monkeypatch.setattr(exporter, "_HAVE_PROM", False)
    exporter.expose_metric("m", 1.0)
    exporter.start_exporter(port=0)


def test_expose_metric_with_prom(monkeypatch):
    """When prom client present, expose_metric updates/create gauge via set()."""
    monkeypatch.setattr(exporter, "_HAVE_PROM", True)

    class FakeG:
        def __init__(self):
            self.value = None

        def set(self, v):
            self.value = v

    # Insert using sanitized metric name to match exporter internal keying
    san = exporter._sanitize_metric_name("m")
    # Ensure exporter module has a Gauge symbol so cast(Gauge, ...) works
    monkeypatch.setattr(exporter, "Gauge", FakeG, raising=False)
    monkeypatch.setitem(exporter._gauges, san, FakeG())
    exporter.expose_metric("m", 2.0)
    assert getattr(exporter._gauges[san], "value", None) == 2.0
