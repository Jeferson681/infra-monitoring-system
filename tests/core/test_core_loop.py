import importlib

from types import SimpleNamespace

core = importlib.import_module("src.core.core")


def test_ensure_runtime_checks_monkeypatch(monkeypatch):
    """Teste para verificação de runtime com monkeypatch."""
    # monkeypatch helpers to raise and ensure function swallows exceptions
    monkeypatch.setattr("src.core.core.ensure_log_dirs_exist", lambda: (_ for _ in ()).throw(Exception("boom")))
    monkeypatch.setattr("src.core.core.ensure_last_ts_exists", lambda: (_ for _ in ()).throw(Exception("boom")))
    # should not raise
    core._ensure_runtime_checks()


def test_collect_and_emit_handles_collect_exceptions(monkeypatch):
    """Teste para coleta e emissão lidando com exceções."""
    fake_state = SimpleNamespace()
    fake_state.evaluate_metrics = lambda m: "STABLE"
    fake_state.current_snapshot = {"a": 1}

    monkeypatch.setattr("src.core.core._collect_metrics", lambda: (_ for _ in ()).throw(Exception("bad")))
    # monkeypatch emitter to be noop
    monkeypatch.setattr("src.core.core._emit_snapshot", lambda s, r, v: None)

    res = core._collect_and_emit(fake_state, verbose_level=0)
    assert res["state"] == "STABLE"


def test_run_loop_one_cycle(monkeypatch):
    """Teste para execução de um ciclo do loop principal."""
    # run only one cycle quickly by setting cycles=1 and interval=0
    monkeypatch.setattr("src.core.core._ensure_runtime_checks", lambda: None)
    monkeypatch.setattr("src.core.core._collect_and_emit", lambda s, v: {"state": "S"})
    monkeypatch.setattr("src.core.core._run_maintenance", lambda now, a, b, c, d, intervals: (a, b, c, d))

    core._run_loop(interval=0, cycles=1, verbose_level=0)
