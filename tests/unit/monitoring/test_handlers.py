def test_import_handlers():
    """Importa o módulo de handlers sem erros."""
    # module should expose attempt_treatment and helper selection
    import inspect

    import infra_monitoring.services.monitoring.handlers as handlers

    assert handlers is not None

    for name in ("attempt_treatment", "_select_action"):
        fn = getattr(handlers, name, None)
        assert fn is not None, f"{name} missing from handlers"
        assert callable(fn), f"{name} must be callable"
        sig = inspect.signature(fn)
        assert len(sig.parameters) >= 1, f"{name} should accept at least 1 parameter"
