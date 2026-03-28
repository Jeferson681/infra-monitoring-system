def test_import_settings():
    """Importa o módulo de settings e verifica símbolos públicos."""
    # module should expose expected constants and callables
    import inspect

    import infra_monitoring.infra.config.settings as settings

    assert hasattr(settings, "METRIC_NAMES") and isinstance(settings.METRIC_NAMES, list)
    assert hasattr(settings, "DEFAULT_THRESHOLDS") and isinstance(
        settings.DEFAULT_THRESHOLDS, dict
    )
    fn = getattr(settings, "load_settings", None)
    assert fn is not None and callable(fn)
    assert len(inspect.signature(fn).parameters) == 0
    fn2 = getattr(settings, "validate_settings", None)
    assert fn2 is not None and callable(fn2)
    assert len(inspect.signature(fn2).parameters) >= 1
