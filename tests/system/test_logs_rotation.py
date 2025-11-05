import os

from src.system import logs as logs_mod
from src.system import log_helpers as lh


def test_try_rotate_file_moves_and_compresses(tmp_path, monkeypatch):
    """Testa se arquivos antigos são rotacionados e comprimidos corretamente."""
    # Create log file and ensure it's old
    root = tmp_path / "logsroot"
    os.environ["MONITORING_LOG_ROOT"] = str(root)
    lp = logs_mod.get_log_paths()
    p = lp.log_dir / "app-2025-10-16.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x")
    # Make file appear old
    os.utime(p, (0, 0))

    # Make compress_file succeed
    monkeypatch.setattr(lh, "compress_file", lambda s, d: True)
    logs_mod.try_rotate_file(p, lp.archive_dir, ".log.gz", day_secs=1, week_secs=7)
    # rotating file should be removed (copmressed)
    rot = lp.archive_dir / (p.name + lh.ROTATING_SUFFIX)
    assert not rot.exists()


def test_compress_old_logs_iterates_rotating(tmp_path, monkeypatch):
    """Testa se compress_old_logs itera e comprime arquivos .rotating."""
    root = tmp_path / "logsroot2"
    os.environ["MONITORING_LOG_ROOT"] = str(root)
    lp = logs_mod.get_log_paths()

    rot = lp.archive_dir / ("oldfile" + lh.ROTATING_SUFFIX)
    rot.parent.mkdir(parents=True, exist_ok=True)
    rot.write_text("x")
    os.utime(rot, (0, 0))

    called = {"count": 0}

    def fake_try_compress_rotating(r, a, d, w):
        called["count"] += 1

    # compress_old_logs uses the local import in logs_mod, so patch that name
    monkeypatch.setattr(logs_mod, "try_compress_rotating", fake_try_compress_rotating)
    logs_mod.compress_old_logs(day_secs=1, week_secs=7)
    assert called["count"] == 1


def test_safe_remove_unlinks_old(tmp_path, monkeypatch):
    """Testa se safe_remove remove arquivos antigos corretamente."""
    root = tmp_path / "logsroot3"
    os.environ["MONITORING_LOG_ROOT"] = str(root)
    lp = logs_mod.get_log_paths()

    gz = lp.archive_dir / ("a.log.gz")
    gz.parent.mkdir(parents=True, exist_ok=True)
    gz.write_text("x")
    os.utime(gz, (0, 0))

    # Make archive_file_is_old return True for the test
    monkeypatch.setattr(lh, "archive_file_is_old", lambda p, now_ts, rd: True)
    logs_mod.safe_remove(retention_days=1, safe_retention_days=2)
    assert not gz.exists()


def test_rotate_logs_calls_try_rotate(tmp_path, monkeypatch):
    """Testa se rotate_logs chama try_rotate_file para cada arquivo relevante."""
    root = tmp_path / "root4"
    os.environ["MONITORING_LOG_ROOT"] = str(root)
    lp = logs_mod.get_log_paths()

    # create a .log and .jsonl
    log_file = lp.log_dir / "a-2025-10-16.log"
    j = lp.json_dir / "b-2025-10-16.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    j.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("x")
    j.write_text("x")

    called = {"count": 0}

    def fake_try_rotate_file(p, a, s, d, e):
        # accept five args (p, archive_dir, gz_suffix, day_secs, week_secs)
        called["count"] += 1

    monkeypatch.setattr(logs_mod, "try_rotate_file", fake_try_rotate_file)
    logs_mod.rotate_logs(day_secs=1, week_secs=7)
    assert called["count"] >= 2
