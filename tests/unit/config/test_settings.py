def test_import_settings():
    """Importa o módulo de settings sem erros."""
    import infra_monitoring.infra.config.settings as settings

    assert settings is not None
