def test_import_settings():
    """Importa o módulo de settings sem erros."""
    import src.config.settings as settings

    assert settings is not None
