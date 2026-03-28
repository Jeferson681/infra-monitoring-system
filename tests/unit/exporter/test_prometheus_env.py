def test_start_exporter_initializes_without_starting_server(monkeypatch):
    """start_exporter deve inicializar métricas, mas não iniciar um servidor HTTP."""
    import infra_monitoring.api.exporter.prometheus as prom

    # Garantir estado limpo
    monkeypatch.setattr(prom, "_server_started", False)

    called = {}

    # Substitui qualquer tentativa de start_http_server por um stub que marque chamada
    def fake_start_http_server(port, addr):
        called["start_http_called"] = True

    monkeypatch.setattr(
        prom, "start_http_server", fake_start_http_server, raising=False
    )

    # Substitui a população inicial de metrics para verificar que foi chamada
    def fake_expose(jsonl_path):
        called["exposed_from_jsonl"] = jsonl_path

    monkeypatch.setattr(prom, "expose_system_metrics_from_jsonl", fake_expose)

    # Chama start_exporter; não deve acionar start_http_server
    prom.start_exporter(port=None, addr=None)

    assert prom._server_started is True
    assert "exposed_from_jsonl" in called
    assert "start_http_called" not in called
    # ensure internal gauges mapping exists
    assert isinstance(getattr(prom, "_gauges", {}), dict)
