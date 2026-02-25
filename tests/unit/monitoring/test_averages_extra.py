"""Extra tests for averages-related behavior (complement to existing tests)."""

import importlib

import infra_monitoring.services.monitoring.formatters as formatters


def test_human_bytes_and_persist_smoke(tmp_path):
    """Smoke test: human byte formatting and persist_last_time produce expected outputs."""
    mod = importlib.import_module("infra_monitoring.services.monitoring.averages")
    assert formatters._fmt_bytes_human(1024**2) == "1.00 MB"
    p = mod.persist_last_time()
    assert p.exists()
