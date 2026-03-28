def test_import_args():
    """Importa o módulo args sem erros."""
    import inspect

    import infra_monitoring.core.args as args

    assert args is not None
    # ensure configure_argparser exists and is callable
    fn = getattr(args, "configure_argparser", None)
    assert fn is not None and callable(fn)
    assert len(inspect.signature(fn).parameters) == 0
