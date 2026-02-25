def test_import_args():
    """Importa o módulo args sem erros."""
    import infra_monitoring.core.args as args

    assert args is not None
