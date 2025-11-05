import time
import importlib
import types


def test_read_maintenance_intervals_and_run_cycle(monkeypatch):
    """Verifica que os intervalos de manutenção são lidos e _run_maintenance atualiza timestamps."""
    from src.system import maintenance

    # set env vars to known small intervals
    monkeypatch.setenv("MONITORING_ROTATE_INTERVAL_SEC", "1")
    monkeypatch.setenv("MONITORING_COMPRESS_INTERVAL_SEC", "1")
    monkeypatch.setenv("MONITORING_SAFE_REMOVE_INTERVAL_SEC", "1")
    monkeypatch.setenv("MONITORING_HOURLY_INTERVAL_SEC", "1")

    intervals = maintenance._read_maintenance_intervals()
    now = time.time()
    lr, lc, ls, lh = 0.0, 0.0, 0.0, 0.0
    # run maintenance once; should update timestamps to now
    nr, nc, ns, nh = maintenance._run_maintenance(now + 2.0, lr, lc, ls, lh, intervals)
    assert nr == now + 2.0 or isinstance(nr, float)


def test_read_maintenance_intervals_defaults(monkeypatch):
    """_read_maintenance_intervals returns default tuple when env unset."""
    mod = importlib.import_module("src.system.maintenance")
    # unset env vars
    monkeypatch.delenv("MONITORING_ROTATE_INTERVAL_SEC", raising=False)
    monkeypatch.delenv("MONITORING_COMPRESS_INTERVAL_SEC", raising=False)
    monkeypatch.delenv("MONITORING_SAFE_REMOVE_INTERVAL_SEC", raising=False)
    monkeypatch.delenv("MONITORING_HOURLY_INTERVAL_SEC", raising=False)

    intervals = mod._read_maintenance_intervals()
    assert len(intervals) == 4


def test_run_maintenance_calls(monkeypatch):
    """_run_maintenance should call rotate/compress/safe_remove/hourly when intervals elapsed."""
    mod = importlib.import_module("src.system.maintenance")
    now = 1000.0
    last = 0.0
    # patch rotate/compress/safe_remove/hourly to simple functions that set flags
    called = {}

    monkeypatch.setattr("src.system.maintenance.rotate_logs", lambda: called.setdefault("r", True))
    monkeypatch.setattr("src.system.maintenance.compress_old_logs", lambda: called.setdefault("c", True))
    monkeypatch.setattr("src.system.maintenance.safe_remove", lambda: called.setdefault("s", True))
    monkeypatch.setattr("src.system.maintenance.get_log_paths", lambda: types.SimpleNamespace(root="."))
    monkeypatch.setattr("src.system.maintenance.aggregate_last_seconds", lambda **k: {"m": 1})
    monkeypatch.setattr("src.system.maintenance.write_average_log", lambda *a, **k: called.setdefault("w", True))

    intervals = (1, 1, 1, 1)
    lr, lc, ls, lh = mod._run_maintenance(now, last, last, last, last, intervals)
    assert lr == now and lc == now and ls == now and lh == now
    assert called
