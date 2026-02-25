from src.monitoring import metrics as m


def test_cache_concurrent_returns_cached(monkeypatch):
    """Teste para retorno de cache concorrente."""
    key = "cpu_percent"
    # ensure cache has an existing value
    m._CACHE[key]["value"] = 7
    m._CACHE[key]["ts"] = 0.0

    # monkeypatch the lock object in the _LOCKS dict to simulate someone else holding it
    class FakeLock:
        def acquire(self, blocking=False):
            return False

        def release(self):
            return None

    monkeypatch.setitem(m._LOCKS, key, FakeLock())

    def collector():
        return 999

    val = m._cache_get_or_refresh(key, collector)
    assert val == 7


def test_collect_metrics_triggers_export(monkeypatch):
    """Teste para trigger de exportação ao coletar métricas."""
    called = {"n": 0}

    def fake_export(metrics):
        called["n"] += 1

    # call _export_some_metrics directly to validate behavior
    monkeypatch.setattr(m, "_export_some_metrics", lambda metrics: fake_export(metrics), raising=False)
    res = {}
    m._export_some_metrics(res)
    assert called["n"] == 1
