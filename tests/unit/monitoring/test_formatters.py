def test_import_formatters():
    """Importa o módulo de formatters sem erros."""
    import infra_monitoring.services.monitoring.formatters as formatters

    assert formatters is not None
