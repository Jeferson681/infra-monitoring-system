import gzip
import json
import os
import sys
import time
import types
from pathlib import Path

# Robustly locate the project's `src` directory and add it to sys.path. This
# keeps tests resilient to different working directories used by runners.
HERE = Path(__file__).resolve()
SRC = None
for parent in [HERE] + list(HERE.parents):
    candidate = parent / "src"
    if (candidate / "system" / "logs.py").exists():
        SRC = candidate
        break
if SRC is None:
    # fallback: assume two levels up + src
    SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _load_logs_module():
    """Load `system.logs` module from the project's src directory.

    This is resilient to different test runner cwd / PYTHONPATH setups.
    """
    import importlib

    try:
        return importlib.import_module("system.logs")
    except Exception:
        # fallback: load module directly from file path
        import importlib.util

        pkg = types.ModuleType("system")
        pkg.__path__ = [str(SRC / "system")]
        sys.modules["system"] = pkg
        file_path = SRC / "system" / "logs.py"
        spec = importlib.util.spec_from_file_location("system.logs", str(file_path))
        module = importlib.util.module_from_spec(spec)
        sys.modules["system.logs"] = module
        spec.loader.exec_module(module)
        return module


def _inject_settings(tmp_path: Path):
    # create a fake config.settings module so get_log_paths reads LOG_ROOT
    config_mod = types.ModuleType("config")
    settings_mod = types.ModuleType("config.settings")
    settings_mod.LOG_ROOT = str(tmp_path / "logs")
    sys.modules["config"] = config_mod
    sys.modules["config.settings"] = settings_mod
    return settings_mod


def test_write_log_creates_files(tmp_path):
    """write_log should create human and jsonl files with expected content."""
    _inject_settings(tmp_path)
    logs = _load_logs_module()

    # write a log entry
    logs.write_log("testapp", "INFO", "hello world", extra={"x": 1})

    lp = logs.get_log_paths()
    log_dir = lp.log_dir
    json_dir = lp.json_dir
    # check human log (now with date suffix)
    from datetime import date

    today = date.today().isoformat()
    human = log_dir / f"testapp-{today}.log"
    assert human.exists()
    content = human.read_text(encoding="utf-8")
    assert "hello world" in content

    # check jsonl
    j = json_dir / f"testapp-{today}.jsonl"
    assert j.exists()
    line = j.read_text(encoding="utf-8").strip()
    obj = json.loads(line)
    assert obj["msg"] == "hello world"
    assert obj["x"] == 1


def test_rotate_and_compress(tmp_path):
    """rotate_logs should move old jsonl into archive and produce .jsonl.gz."""
    _inject_settings(tmp_path)
    logs = _load_logs_module()

    lp = logs.get_log_paths()
    json_dir = lp.json_dir
    archive_dir = lp.archive_dir

    # create an old entries file
    fname = "entries-2020-01-01.jsonl"
    p = json_dir / fname
    p.write_text('{"ts":"x","level":"I","msg":"old"}\n', encoding="utf-8")
    # make it old (2 days)
    old_at = time.time() - (2 * 24 * 60 * 60)
    os.utime(p, (old_at, old_at))

    # run rotation
    logs.rotate_logs()

    # after rotation+compress we expect a .jsonl.gz in archive with base name
    gz = archive_dir / "entries-2020-01-01.jsonl.gz"
    assert gz.exists()

    # check gz content decodes to original data
    with gzip.open(gz, "rt", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    assert len(lines) == 1
    o = json.loads(lines[0])
    assert o["msg"] == "old"


def test_compress_old_rotating(tmp_path):
    """compress_old_logs should compress existing .rotating files."""
    _inject_settings(tmp_path)
    logs = _load_logs_module()

    lp = logs.get_log_paths()
    archive_dir = lp.archive_dir

    # create a rotating file that is old enough
    rotating = archive_dir / "entries-2019.jsonl.rotating"
    rotating.write_text('{"ts":"x","level":"I","msg":"rot"}\n', encoding="utf-8")
    old_at = time.time() - (2 * 24 * 60 * 60)
    os.utime(rotating, (old_at, old_at))

    logs.compress_old_logs()

    gz = archive_dir / "entries-2019.jsonl.gz"
    assert gz.exists()
    assert not rotating.exists()


def test_safe_remove_respects_safe_retention(tmp_path):
    """safe_remove should remove files older than configured retention."""
    _inject_settings(tmp_path)
    logs = _load_logs_module()

    lp = logs.get_log_paths()
    archive_dir = lp.archive_dir

    # create two gz files, one safe and one normal
    normal = archive_dir / "a.jsonl.gz"
    safe = archive_dir / "b_safe.jsonl.gz"
    normal.write_text("x", encoding="utf-8")
    safe.write_text("x", encoding="utf-8")
    # set normal to be older than 1 day, safe to be older than 10 days
    now = time.time()
    os.utime(normal, (now - (2 * 24 * 60 * 60), now - (2 * 24 * 60 * 60)))
    os.utime(safe, (now - (11 * 24 * 60 * 60), now - (11 * 24 * 60 * 60)))

    # remove with retention_days=1 and safe_retention_days=10
    logs.safe_remove(retention_days=1, safe_retention_days=10)

    assert not normal.exists()
    assert not safe.exists()


# Testes para rotação, compressão e persistência de logs
