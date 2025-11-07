import sys


from src.monitoring import metrics as m


def test_reset_cache_timestamps_and_is_stale():
    """Teste para reset de timestamps do cache e verificação de stale."""
    """Teste para reset de timestamps do cache e verificação de stale."""
    # populate cache with a value and old timestamp
    m._CACHE["cpu_percent"]["value"] = 1.23
    m._CACHE["cpu_percent"]["ts"] = 0.0
    assert m._is_stale("cpu_percent") is True
    m._reset_cache_timestamps()
    assert m._CACHE["cpu_percent"]["ts"] == 0.0


def test_cache_get_or_refresh_calls_collector(monkeypatch):
    """Teste para chamada do coletor ao atualizar cache."""
    """Teste para chamada do coletor ao atualizar cache."""
    calls = {"n": 0}

    def collector(x):
        calls["n"] += 1
        return x * 2

    # unknown key should call collector directly
    assert m._cache_get_or_refresh("unknown_key", collector, 3) == 6

    # known key but stale should call collector and update cache
    key = "cpu_percent"
    m._CACHE[key]["ts"] = 0.0
    val = m._cache_get_or_refresh(key, lambda: 9)
    assert val == 9
    assert m._CACHE[key]["value"] == 9


def test_export_some_metrics_with_prom(monkeypatch):
    """Teste para exportação de métricas com Prometheus."""
    """Teste para exportação de métricas com Prometheus."""
    # Prepare metrics dict with values
    metrics = {"cpu_percent": 10.0, "memory_percent": 20.0, "disk_percent": 30.0}

    # Create a fake exporter module with expose_metric
    class FakeExp:
        def __init__(self):
            self.calls = []

        def expose_metric(self, name, value, description=None):
            self.calls.append((name, value, description))

    fake = FakeExp()
    # Insert fake module into sys.modules so import works inside function
    sys.modules["src.exporter.prometheus"] = fake

    try:
        m._export_some_metrics(metrics)
        # ensure three metrics exposed
        assert len(fake.calls) == 3
        names = [c[0] for c in fake.calls]
        assert "monitoring_cpu_percent" in names
    finally:
        del sys.modules["src.exporter.exporter"]


def test_export_some_metrics_no_prom(monkeypatch):
    """Teste para exportação de métricas sem Prometheus."""
    """Teste para exportação de métricas sem Prometheus."""
    # If exporter import fails, function should silently continue
    metrics = {"cpu_percent": None, "memory_percent": None, "disk_percent": None}
    # ensure no module present
    if "src.exporter.exporter" in sys.modules:
        del sys.modules["src.exporter.exporter"]
    # Should not raise
    m._export_some_metrics(metrics)
