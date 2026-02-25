def test_import_core():
    """Importa o core sem erros."""
    import src.core.core as core

    assert core is not None
