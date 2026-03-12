import logging
import sys
import os
from types import SimpleNamespace

import pytest

import main as main_mod


def test_get_json_formatter_includes_exc():
    fmt = main_mod._get_json_formatter()
    logger = logging.getLogger("test_json_fmt")
    try:
        raise ValueError("boom")
    except Exception:
        record = logging.LogRecord(
            name=logger.name,
            level=logging.ERROR,
            pathname=__file__,
            lineno=10,
            msg="oops",
            args=(),
            exc_info=sys.exc_info(),
        )
    out = fmt.format(record)
    assert "\"level\": \"ERROR\"" in out
    assert "ValueError" in out


def test_has_existing_file_handler_and_wrap(tmp_path):
    # create temp files
    p = tmp_path / "debug.log"
    j = tmp_path / "debug.jsonl"

    fh = logging.FileHandler(str(p))
    jfh = logging.FileHandler(str(j))

    root = logging.getLogger("test_root")
    # ensure clean
    root.handlers = []

    assert not main_mod._has_existing_file_handler(root, fh, jfh)

    # attach one handler and test detection
    root.addHandler(fh)
    assert main_mod._has_existing_file_handler(root, fh, jfh)

    # test wrap_emit_safe - create handler whose emit raises
    class DummyHandler:
        def emit(self, record):
            raise RuntimeError("boom")

    dh = DummyHandler()
    # monkeypatch by calling wrapper directly
    main_mod._wrap_emit_safe(dh)
    # calling emit should not raise
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "m", (), None)
    dh.emit(record)


def test_main_starts_components(monkeypatch):
    called = {}

    def fake_parse_args(argv):
        return SimpleNamespace(interval=1, cycles=0, verbose=0)

    # patch the names imported into main module (they were imported at module load)
    monkeypatch.setattr(main_mod, "parse_args", fake_parse_args)
    monkeypatch.setattr(main_mod, "get_log_config", lambda args: {"level": "INFO"})

    # avoid real file handlers
    monkeypatch.setattr(main_mod, "_setup_debug_file_handler", lambda: None)
    monkeypatch.setattr(main_mod, "ensure_default_last_ts", lambda: None)

    # stub exporter start
    monkeypatch.setattr("infra_monitoring.api.exporter.prometheus.start_exporter", lambda: called.setdefault("exporter", True))

    # stub http and promtail functions
    monkeypatch.setattr("infra_monitoring.api.exporter.main_http.run_http_server", lambda **kwargs: called.setdefault("http", True))
    monkeypatch.setattr("infra_monitoring.api.exporter.main_http.run_promtail_worker", lambda: called.setdefault("promtail", True))

    # replace threading.Thread to avoid starting threads
    class DummyThread:
        def __init__(self, *args, **kwargs):
            # capture target and kwargs if provided
            self._target = kwargs.get("target") if "target" in kwargs else (args[0] if args else None)
            self._tkwargs = kwargs.get("kwargs", {})
            called.setdefault("thread_created", True)

        def start(self):
            called.setdefault("thread_started", True)
            if callable(self._target):
                try:
                    self._target(**self._tkwargs)
                except TypeError:
                    # target may expect no kwargs or different signature
                    try:
                        self._target()
                    except Exception:
                        pass

    monkeypatch.setattr("threading.Thread", DummyThread)

    # stub run_loop to capture call - patch the reference used by main module
    def fake_run_loop(interval, cycles, verbose_level):
        called["run_loop"] = (interval, cycles, verbose_level)

    monkeypatch.setattr(main_mod, "run_loop", fake_run_loop)

    # enable exporter and http in env
    monkeypatch.setenv("MONITORING_EXPORTER_ENABLE", "1")
    monkeypatch.setenv("MONITORING_HTTP_ENABLE", "1")
    monkeypatch.setenv("MONITORING_PROMTAIL_ENABLE", "1")

    # call main with empty argv to trigger default behavior
    main_mod.main(argv=[])

    assert "run_loop" in called
    assert called.get("exporter") is True
    assert called.get("http") is True


def test_main_loads_env_and_parse_args_none(monkeypatch, tmp_path):
    # ensure env file is read and values applied when argv is None
    called = {}

    def fake_parse_args(argv):
        # expect None
        called["parse_called_with"] = argv
        return SimpleNamespace(interval=1, cycles=0, verbose=0)

    monkeypatch.setattr(main_mod, "parse_args", fake_parse_args)
    monkeypatch.setattr(main_mod, "get_log_config", lambda args: {"level": "INFO"})
    monkeypatch.setattr(main_mod, "_setup_debug_file_handler", lambda: None)
    monkeypatch.setattr(main_mod, "ensure_default_last_ts", lambda: None)

    # monkeypatch helpers to simulate .env file
    monkeypatch.setattr(
        "infra_monitoring.infra.system.helpers.get_project_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        "infra_monitoring.infra.system.helpers.read_env_file", lambda p: {"XTEST": "1"}
    )

    # stub run_loop so we return quickly
    monkeypatch.setattr(main_mod, "run_loop", lambda interval, cycles, verbose_level: called.setdefault("run_loop", True))

    # ensure env var not present
    monkeypatch.delenv("XTEST", raising=False)
    main_mod.main(argv=None)
    assert os.environ.get("XTEST") == "1"


def test_main_setup_debug_file_handler_exception(monkeypatch):
    # ensure errors from _setup_debug_file_handler are caught
    monkeypatch.setattr(main_mod, "parse_args", lambda a: SimpleNamespace(interval=1, cycles=0, verbose=0))
    monkeypatch.setattr(main_mod, "get_log_config", lambda args: {"level": "INFO"})
    monkeypatch.setattr(main_mod, "_setup_debug_file_handler", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(main_mod, "ensure_default_last_ts", lambda: None)
    monkeypatch.setattr(main_mod, "run_loop", lambda interval, cycles, verbose_level: None)
    # should not raise
    main_mod.main(argv=[])


def test_main_exporter_raises_and_http_addr(monkeypatch):
    called = {}
    monkeypatch.setattr(main_mod, "parse_args", lambda a: SimpleNamespace(interval=1, cycles=0, verbose=0))
    monkeypatch.setattr(main_mod, "get_log_config", lambda args: {"level": "INFO"})
    monkeypatch.setattr(main_mod, "_setup_debug_file_handler", lambda: None)
    monkeypatch.setattr(main_mod, "ensure_default_last_ts", lambda: None)

    # exporter exists but raises
    def bad_exporter():
        raise RuntimeError("fail")

    monkeypatch.setattr("infra_monitoring.api.exporter.prometheus.start_exporter", bad_exporter)

    # capture run_http_server kwargs
    def fake_run_http_server(**kwargs):
        called["http_kwargs"] = kwargs

    monkeypatch.setattr("infra_monitoring.api.exporter.main_http.run_http_server", fake_run_http_server)

    # thread that calls target synchronously
    class DummyThread2:
        def __init__(self, *args, **kwargs):
            self._target = kwargs.get("target") if "target" in kwargs else (args[0] if args else None)
            self._tkwargs = kwargs.get("kwargs", {})

        def start(self):
            if callable(self._target):
                try:
                    self._target(**self._tkwargs)
                except TypeError:
                    self._target()

    monkeypatch.setattr("threading.Thread", DummyThread2)

    monkeypatch.setenv("MONITORING_EXPORTER_ENABLE", "1")
    monkeypatch.setenv("MONITORING_HTTP_ENABLE", "1")
    monkeypatch.setenv("MONITORING_HTTP_ADDR", "0.0.0.0")
    monkeypatch.setattr(main_mod, "run_loop", lambda *a, **k: None)

    # run main
    main_mod.main(argv=[])
    assert called.get("http_kwargs", {}).get("addr") == "0.0.0.0"


def test_main_env_load_exception(monkeypatch):
    # simulate get_project_root raising when called so env load fails
    monkeypatch.setattr(
        "infra_monitoring.infra.system.helpers.get_project_root",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    # stub parse_args/run_loop to exit quickly
    monkeypatch.setattr(main_mod, "parse_args", lambda a: SimpleNamespace(interval=1, cycles=0, verbose=0))
    monkeypatch.setattr(main_mod, "get_log_config", lambda args: {"level": "INFO"})
    monkeypatch.setattr(main_mod, "_setup_debug_file_handler", lambda: None)
    monkeypatch.setattr(main_mod, "ensure_default_last_ts", lambda: None)
    monkeypatch.setattr(main_mod, "run_loop", lambda *a, **k: None)
    # should not raise
    main_mod.main(argv=[])


def test_main_exporter_importerror_and_promtail_inner(monkeypatch):
    # Simulate prometheus module present but missing start_exporter -> ImportError
    import types as _types, sys as _sys

    mod = _types.ModuleType("infra_monitoring.api.exporter.prometheus")
    _sys.modules["infra_monitoring.api.exporter.prometheus"] = mod

    # Ensure main uses our parse_args and run_loop
    monkeypatch.setattr(main_mod, "parse_args", lambda a: SimpleNamespace(interval=1, cycles=0, verbose=0))
    monkeypatch.setattr(main_mod, "get_log_config", lambda args: {"level": "INFO"})
    monkeypatch.setattr(main_mod, "_setup_debug_file_handler", lambda: None)
    monkeypatch.setattr(main_mod, "ensure_default_last_ts", lambda: None)

    # For promtail inner import, provide main_http module without run_promtail_worker
    mod2 = _types.ModuleType("infra_monitoring.api.exporter.main_http")
    # provide run_http_server to avoid failure
    def fake_http(**kwargs):
        return None

    mod2.run_http_server = fake_http
    _sys.modules["infra_monitoring.api.exporter.main_http"] = mod2

    # Dummy thread that calls target
    class SyncThread:
        def __init__(self, *args, **kwargs):
            self._target = kwargs.get("target") if "target" in kwargs else (args[0] if args else None)
            self._tkwargs = kwargs.get("kwargs", {})

        def start(self):
            if callable(self._target):
                try:
                    self._target(**self._tkwargs)
                except TypeError:
                    self._target()

    monkeypatch.setattr("threading.Thread", SyncThread)
    monkeypatch.setattr(main_mod, "run_loop", lambda *a, **k: None)
    monkeypatch.setenv("MONITORING_EXPORTER_ENABLE", "1")
    monkeypatch.setenv("MONITORING_HTTP_ENABLE", "1")
    monkeypatch.setenv("MONITORING_PROMTAIL_ENABLE", "1")

    # should not raise despite missing start_exporter and missing promtail worker
    main_mod.main(argv=[])


def test_main_thread_init_raises(monkeypatch):
    # Make threading.Thread constructor raise to hit outer except
    class BadThread:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("bad init")

    monkeypatch.setattr("threading.Thread", BadThread)
    monkeypatch.setattr(main_mod, "parse_args", lambda a: SimpleNamespace(interval=1, cycles=0, verbose=0))
    monkeypatch.setattr(main_mod, "get_log_config", lambda args: {"level": "INFO"})
    monkeypatch.setattr(main_mod, "_setup_debug_file_handler", lambda: None)
    monkeypatch.setattr(main_mod, "ensure_default_last_ts", lambda: None)
    monkeypatch.setattr(main_mod, "run_loop", lambda *a, **k: None)
    monkeypatch.setenv("MONITORING_HTTP_ENABLE", "1")

    # should not raise
    main_mod.main(argv=[])
