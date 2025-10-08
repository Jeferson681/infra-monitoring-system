def test_import_exporter():
    """Importa o exporter sem erros."""
    import src.exporter.exporter as exporter

    assert exporter is not None
