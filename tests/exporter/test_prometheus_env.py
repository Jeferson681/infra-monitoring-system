def test_start_exporter_reads_env(monkeypatch):
    """Verifica que start_exporter usa MONITORING_EXPORTER_ADDR/PORT quando args forem None."""
    import src.exporter.prometheus as prom

    # Garantir que a flag de disponibilidade seja verdadeira para o teste
    monkeypatch.setattr(prom, "_HAVE_PROM", True)
    monkeypatch.setattr(prom, "_server_started", False)

    monkeypatch.setenv("MONITORING_EXPORTER_ADDR", "0.0.0.0")
    monkeypatch.setenv("MONITORING_EXPORTER_PORT", "12345")

    called = {}

    def fake_start_http_server(port, addr):
        called["port"] = port
        called["addr"] = addr

    # Substitui a função real por um stub
    monkeypatch.setattr(prom, "start_http_server", fake_start_http_server)

    # Chama com None para que os valores venham do ambiente
    prom.start_exporter(port=None, addr=None)

    assert called.get("port") == 12345
    assert called.get("addr") == "0.0.0.0"
