def test_import_handlers():
    """Importa o módulo de handlers sem erros."""
    import infra_monitoring.services.monitoring.handlers as handlers

    assert handlers is not None
