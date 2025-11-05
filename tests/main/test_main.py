import importlib


def test_main_initializes(monkeypatch, tmp_path):
    """Main should initialize logging and call ensure_default_last_ts without side-effects."""
    monkeypatch.setenv("MONITORING_LOG_ROOT", str(tmp_path))
    # prevent long runs: make _run_loop a noop
    monkeypatch.setattr("src.main._run_loop", lambda *a, **k: None)
    monkeypatch.setenv("MONITORING_EXPORTER_ENABLE", "0")
    from src.main import main

    main(["--cycles", "1"])  # should not raise


def test_main_initialization(monkeypatch, tmp_path):
    """Main should call setup_debug handler, ensure_default_last_ts and optionally start exporter."""
    mod = importlib.import_module("src.main")

    # avoid running the real _run_loop
    monkeypatch.setattr("src.main._run_loop", lambda **k: None)

    # make ensure_default_last_ts a no-op
    monkeypatch.setattr("src.main.ensure_default_last_ts", lambda: None)

    # avoid actual file handler creation by monkeypatching get_debug_file_path
    monkeypatch.setattr("src.main.get_debug_file_path", lambda: tmp_path / "debug.log")

    # ensure exporter is not started unless env var set
    monkeypatch.delenv("MONITORING_EXPORTER_ENABLE", raising=False)

    # parse_args expects argv without the program name
    mod.main(argv=["--cycles", "1"])


def test_setup_debug_file_handler_sets_handler_and_hook(monkeypatch, tmp_path):
    """_setup_debug_file_handler deve adicionar FileHandler e configurar exceção global sem erro."""
    import src.main as main_mod

    # Monkeypatch get_debug_file_path para evitar escrita real
    monkeypatch.setattr(main_mod, "get_debug_file_path", lambda: tmp_path / "debug.log")

    # Limpar handlers existentes para isolar o teste
    root = main_mod._logging.getLogger()
    root.handlers = []

    # Executa função
    main_mod._setup_debug_file_handler()

    # Verifica se FileHandler foi adicionado
    assert any(isinstance(h, main_mod._logging.FileHandler) for h in root.handlers)

    # Verifica se excepthook foi configurado
    assert main_mod.sys.excepthook.__name__ == "_exc_hook"
