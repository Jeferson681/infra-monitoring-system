def test_import_handlers():
    """Importa o módulo de handlers sem erros."""
    import src.monitoring.handlers as handlers

    assert handlers is not None
