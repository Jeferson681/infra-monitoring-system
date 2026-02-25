def test_write_debug_entry(tmp_path, monkeypatch):
    """Verifica que uma entrada DEBUG é escrita em .log e .jsonl via write_log.

    Usa MONITORING_LOG_ROOT apontando para tmp_path para isolar efeitos.
    """
    monkeypatch.setenv("MONITORING_LOG_ROOT", str(tmp_path))

    # Import local após setenv para garantir get_log_paths usa MONITORING_LOG_ROOT
    from src.system.logs import write_log, get_log_paths

    # Execute a escrita: humana + json
    write_log(
        "unit-test-debug",
        "DEBUG",
        "mensagem-debug-de-teste",
        extra={"x": 1},
        human_enable=True,
        json_enable=True,
    )

    lp = get_log_paths()

    # Verifica existência de arquivos .log e .jsonl
    logs = sorted(lp.log_dir.glob("unit-test-debug-*.log"))
    jsons = sorted(lp.json_dir.glob("unit-test-debug-*.jsonl"))

    assert logs, f"arquivo .log não criado em {lp.log_dir}"
    assert jsons, f"arquivo .jsonl não criado em {lp.json_dir}"

    # Conteúdo mínimo esperado
    with logs[0].open("r", encoding="utf-8") as f:
        text = f.read()
    assert "mensagem-debug-de-teste" in text

    with jsons[0].open("r", encoding="utf-8") as f:
        j = f.read()
    assert "mensagem-debug-de-teste" in j
