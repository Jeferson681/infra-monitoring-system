def test_import_tray():
    """Importa o módulo tray sem erros."""
    import src.core.tray as tray

    assert tray is not None
