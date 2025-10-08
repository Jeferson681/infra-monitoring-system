def test_import_metrics():
    """Importa o módulo de métricas sem erros."""
    import src.monitoring.metrics as metrics

    assert metrics is not None
