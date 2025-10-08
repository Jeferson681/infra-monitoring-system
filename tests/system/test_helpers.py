def test_import_helpers():
    """Importa o módulo de helpers do sistema sem erros."""
    import src.system.helpers as helpers

    assert helpers is not None
