def test_import_state():
    """Importa o módulo state sem erros."""
    import src.monitoring.state as state

    assert state is not None
