import src.monitoring.formatters as formatters


def test_normalize_for_display_basic():
    """Teste para normalização básica para exibição."""
    """Teste para normalização básica para exibição."""
    metrics = {"cpu": 1.5, "mem": 2.0}
    out = formatters.normalize_for_display(metrics)
    assert isinstance(out, dict)
    assert "metrics_raw" in out
    assert "cpu" in out["metrics_raw"] and "mem" in out["metrics_raw"]


def test_format_duration():
    """Teste para formatação de duração."""
    """Teste para formatação de duração."""
    # Aceita tanto o formato antigo quanto o novo (timedelta padrão)
    result = formatters.format_duration(65)
    assert result == "1m 5s" or result == "0:01:05"
    # Aceita tanto o formato antigo quanto o novo (timedelta padrão)
    result = formatters.format_duration(3600)
    assert result == "1h 0m 0s" or result == "1:00:00"
