def test_import_formatters():
    """Importa o módulo de formatters sem erros."""
    # module should expose expected formatter functions and stable signatures
    import inspect

    import infra_monitoring.services.monitoring.formatters as formatters

    assert formatters is not None

    funcs = [
        ("normalize_for_display", 1),
        ("format_duration", 1),
        ("_fmt_bytes_human", 1),
    ]

    for name, min_args in funcs:
        fn = getattr(formatters, name, None)
        assert fn is not None, f"{name} not found in formatters"
        assert callable(fn), f"{name} should be callable"
        sig = inspect.signature(fn)
        # require at least the expected number of positional or keyword parameters
        assert (
            len(sig.parameters) >= min_args
        ), f"{name} should accept at least {min_args} parameter(s); got {len(sig.parameters)}"
