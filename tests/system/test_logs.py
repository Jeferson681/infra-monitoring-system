def test_import_logs():
    """Importa o módulo de logs sem erros."""
    import src.system.logs as logs

    assert logs is not None
