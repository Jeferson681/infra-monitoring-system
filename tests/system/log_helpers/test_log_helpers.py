import gzip
import os
import time
import importlib

mod = importlib.import_module("src.system.log_helpers")


def test_sanitize_and_normalize():
    """sanitize_log_name e normalize_message_for_human comportam-se como esperado."""
    assert mod.sanitize_log_name("../etc/passwd") != "../etc/passwd"
    assert mod.sanitize_log_name("") == "debug_log"
    long_name = "a" * 500
    assert len(mod.sanitize_log_name(long_name)) <= 200

    assert mod.normalize_message_for_human(None) == ""
    assert "no-newline" in mod.normalize_message_for_human("no-newline")


def test_build_json_entry_and_human_line():
    """Smoke: auto-added docstring for consolidation."""
    js = mod.build_json_entry("2025-01-01T00:00:00", "INFO", "msg", extra={"a": 1})
    assert js["ts"].startswith("2025")
    assert js["level"] == "INFO"
    assert js["msg"] == "msg"


def test_write_text_with_and_without_portalocker(tmp_path, monkeypatch):
    """Smoke: auto-added docstring for consolidation."""
    p = tmp_path / "t.log"

    class FakePL:
        LOCK_EX = 1

        @staticmethod
        def lock(fh, flags):
            return None

        @staticmethod
        def unlock(fh):
            return None

    # Case 1: portalocker present
    monkeypatch.setattr(mod, "portalocker", FakePL)
    mod.write_text(p, "hello\n")
    assert p.read_text(encoding="utf-8").strip() == "hello"

    # Case 2: portalocker absent -> should still write
    monkeypatch.setattr(mod, "portalocker", None)
    mod.write_text(p, "world\n")
    assert "world" in p.read_text(encoding="utf-8")


def test_write_json_fallback(tmp_path):
    """Smoke: auto-added docstring for consolidation."""
    p = tmp_path / "j.jsonl"
    # sets are not JSON serializable; write_json should fallback using str
    mod.write_json(p, {"x": {1, 2}})
    content = p.read_text(encoding="utf-8")
    assert "set(" in content or "{1, 2}" in content


def test_atomic_move_and_compress(tmp_path):
    """Smoke: auto-added docstring for consolidation."""
    src = tmp_path / "src.txt"
    src.write_text("payload")
    dst_rot = tmp_path / "archive" / (src.name + ".rotating")

    # Should be able to move
    ok = mod.atomic_move_to_archive(src, dst_rot)
    assert ok
    assert dst_rot.exists()

    # Create a file to compress
    src2 = tmp_path / "data.txt"
    src2.write_text("abc")
    gz = tmp_path / "out" / "data.txt.gz"
    ok2 = mod.compress_file(src2, gz)
    assert ok2
    assert gz.exists()
    # verify gzip header
    with gzip.open(gz, "rb") as f:
        assert f.read() == b"abc"

    # is_older_than: adjust mtime to past
    older = tmp_path / "old.txt"
    older.write_text("x")
    past = time.time() - 3600
    os.utime(older, (past, past))
    assert mod.is_older_than(older, 10)


def test_ensure_dir_writable(tmp_path):
    """Smoke: auto-added docstring for consolidation."""
    d = tmp_path / "subdir"
    assert mod.ensure_dir_writable(d)
    assert d.exists()


def test_sanitize_log_name_basic():
    """Smoke: auto-added docstring for consolidation."""
    assert mod.sanitize_log_name("normal-name.log") == "normal-name.log"
    assert mod.sanitize_log_name("../../etc/passwd") == "passwd"


def test_build_human_line_legacy_and_multiline(monkeypatch):
    """Smoke: auto-added docstring for consolidation."""
    ts = "2025-10-15T12:00:00Z"
    monkeypatch.delenv("MONITORING_HUMAN_MULTILINE", raising=False)
    s0 = mod.build_human_line(ts, "INFO", "hello world", extras={"a": 1})
    assert "hello world" in s0 and s0.rstrip("\n") == s0[:-1]

    s = mod.build_human_line(ts, "INFO", "hello\nworld", extras={"a": 1})
    assert s.count("\n") >= 2

    monkeypatch.setenv("MONITORING_HUMAN_MULTILINE", "1")
    s2 = mod.build_human_line(ts, "INFO", "hello\nworld", extras={"a": 1})
    assert s2.count("\n") >= 2


def test_normalize_message_for_human_and_truncate():
    """Smoke: auto-added docstring for consolidation."""
    assert mod.normalize_message_for_human(None) == ""
    assert mod.normalize_message_for_human("long\nline").startswith("long")


def test_format_date_for_log():
    """Smoke: auto-added docstring for consolidation."""
    d = time.localtime()
    assert mod.format_date_for_log(d) is not None


def test_is_older_than_and_ensure_dir_writable(tmp_path):
    """Smoke: auto-added docstring for consolidation."""
    f = tmp_path / "t.txt"
    f.write_text("x")
    assert mod.ensure_dir_writable(tmp_path)
    assert not mod.is_older_than(f, 9999999)


# --- MERGED FROM test_log_helpers_all.py: test_sanitize_log_name_fallback ---
def test_sanitize_log_name_fallback():
    """Smoke: auto-added docstring for consolidation."""
    assert mod.sanitize_log_name("") == "debug_log"
    assert mod.sanitize_log_name("normal_name") == "normal_name"


# --- MERGED FROM test_log_helpers_all.py: test_format_date_and_is_older_than ---
def test_format_date_and_is_older_than(tmp_path):
    """Smoke: auto-added docstring for consolidation."""
    p = tmp_path / "f.txt"
    p.write_text("x")
    assert isinstance(mod.format_date_for_log(), str)
    assert mod.is_older_than(p, 3600) is False
    # set mtime to old
    old = time.time() - 3600 * 24
    os.utime(p, (old, old))
    assert mod.is_older_than(p, 3600) is True


# --- MERGED FROM test_log_helpers_batch.py: test_sanitize_and_normalize_and_builders ---
def test_sanitize_and_normalize_and_builders():
    """Smoke: auto-added docstring for consolidation."""
    assert mod.sanitize_log_name("..bad/name!!") != ""
    assert " " not in mod.sanitize_log_name("name with space")
    assert mod.normalize_message_for_human("a\nb") == "a b"
    assert mod.normalize_message_for_human(None) == ""
    ts = "2025-10-15"
    entry = mod.build_json_entry(ts, "INFO", "msg", {"k": "v"})
    assert entry["ts"] == ts and entry["msg"] == "msg"
    human = mod.build_human_line(ts, "WARN", "hello", {"a": 1})
    assert ts in human and "WARN" in human


# --- MERGED FROM test_log_helpers_batch.py: test_ensure_dir_writable_and_write_text ---
def test_ensure_dir_writable_and_write_text(tmp_path):
    """Smoke: auto-added docstring for consolidation."""
    d = tmp_path / "logs"
    assert mod.ensure_dir_writable(d) is True
    p = d / "t.txt"
    mod.write_text(p, "x\n")
    assert p.exists()
    p.unlink()


# --- MERGED FROM test_log_helpers_cleanup_more.py: test_atomic_move_cleanup_when_dst_exists ---
def test_atomic_move_cleanup_when_dst_exists(tmp_path, monkeypatch):
    """Smoke: auto-added docstring for consolidation."""
    s = tmp_path / "s.txt"
    s.write_text("s")
    archive = tmp_path / "archive"
    archive.mkdir()
    dst = archive / (s.name + mod.ROTATING_SUFFIX)
    dst.write_text("old")
    monkeypatch.setattr(mod, "_attempt_rename", lambda a, b: False)
    monkeypatch.setattr(mod, "_attempt_replace", lambda a, b: False)
    monkeypatch.setattr(mod, "_copy_replace_fallback", lambda a, b: False)
    s.unlink()
    res = mod.atomic_move_to_archive(s, dst)
    assert res is False


# --- MERGED FROM test_log_helpers_edge_cases.py: test_atomic_move_backoff_and_cleanup ---
def test_atomic_move_backoff_and_cleanup(tmp_path, monkeypatch):
    """Smoke: auto-added docstring for consolidation."""
    s = tmp_path / "s.txt"
    s.write_text("s")
    archive = tmp_path / "archive"
    archive.mkdir()
    dst = archive / (s.name + mod.ROTATING_SUFFIX)
    monkeypatch.setattr(mod, "_attempt_rename", lambda a, b: False)
    monkeypatch.setattr(mod, "_attempt_replace", lambda a, b: False)
    monkeypatch.setattr(mod, "_copy_replace_fallback", lambda a, b: False)
    assert mod.atomic_move_to_archive(s, dst) is False
