"""Unit tests for src.monitoring.metrics.

Smoke tests covering collect_metrics, _export_some_metrics (with/without prometheus_client)
and a few helper functions.
"""

import importlib
import sys


def test_collect_metrics_smoke():
    """collect_metrics should return a dict with expected keys."""
    mod = importlib.reload(importlib.import_module("src.monitoring.metrics"))
    metrics = mod.collect_metrics()
    assert isinstance(metrics, dict)
    assert "cpu_percent" in metrics and "memory_percent" in metrics


def test_export_some_metrics_no_prom(monkeypatch, caplog):
    """When prometheus_client missing, _export_some_metrics should be a no-op (logs debug)."""
    monkeypatch.setitem(sys.modules, "prometheus_client", None)
    mod = importlib.reload(importlib.import_module("src.monitoring.metrics"))
    caplog.set_level("DEBUG")
    mod._export_some_metrics({"cpu_percent": 1.2, "memory_percent": 3.4, "disk_percent": 5.6})
    # ensure no ERROR logs were emitted
    assert not any(r.levelname == "ERROR" for r in caplog.records)


def test_export_some_metrics_with_prom(monkeypatch):
    """With a fake prometheus_client, expose_metric should be called via exporter."""
    calls = []

    def fake_expose(name, value, description=""):
        calls.append((name, float(value)))

    exporter_mod = importlib.import_module("src.exporter.exporter")
    monkeypatch.setattr(exporter_mod, "expose_metric", fake_expose)
    mod = importlib.reload(importlib.import_module("src.monitoring.metrics"))
    mod._export_some_metrics({"cpu_percent": 2.0, "memory_percent": 4.0, "disk_percent": 6.0})
    assert any("monitoring_cpu_percent" in c[0] for c in calls)
