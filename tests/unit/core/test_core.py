def test_import_core():
    """Importa o core sem erros."""
    # module should expose orchestration entrypoints
    import inspect

    import infra_monitoring.core.core as core

    assert core is not None
    fn = getattr(core, "run_loop", None)
    assert fn is not None and callable(fn)
    assert len(inspect.signature(fn).parameters) >= 0
    fn2 = getattr(core, "_collect_and_emit", None)
    assert fn2 is not None and callable(fn2)
