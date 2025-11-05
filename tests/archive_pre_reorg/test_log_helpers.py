import gzip
import os
import time


def test_sanitize_and_normalize():
    """sanitize_log_name e normalize_message_for_human comportam-se como esperado."""
    from src.system.log_helpers import sanitize_log_name, normalize_message_for_human

    assert sanitize_log_name("../etc/passwd") != "../etc/passwd"
    assert sanitize_log_name("") == "debug_log"
    long_name = "a" * 500
    assert len(sanitize_log_name(long_name)) <= 200

    assert normalize_message_for_human(None) == ""
    assert "no-newline" in normalize_message_for_human("no-newline")


def test_build_json_entry_and_human_line(monkeypatch):
    """build_json_entry cria dicionário e build_human_line alterna legacy/multiline."""
    from src.system.log_helpers import build_json_entry, build_human_line

    j = build_json_entry("ts", "INFO", "ok", {"a": 1, "msg": "shadow"})
    # existing keys should be preserved and collisions renamed
    assert j["ts"] == "ts"
    assert j["level"] == "INFO"
    assert "extra_msg" in j

    # Legacy single-line
    monkeypatch.delenv("MONITORING_HUMAN_MULTILINE", raising=False)
    line = build_human_line("2020-01-01T00:00:00Z", "INFO", "message", {"x": 1})
    assert line.endswith("\n") and "message" in line and "x=1" in line

    # For a message containing newline, multiline should be used even if env not set
    multi = build_human_line("2020-01-01T00:00:00Z", "INFO", "a\nb", {"y": 2})
    assert "\n\n" in multi


def test_write_text_with_and_without_portalocker(tmp_path, monkeypatch):
    """write_text deve gravar com e sem portalocker."""
    from src.system import log_helpers as lh

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
    monkeypatch.setattr(lh, "portalocker", FakePL)
    lh.write_text(p, "hello\n")
    assert p.read_text(encoding="utf-8").strip() == "hello"

    # Case 2: portalocker absent -> should still write
    monkeypatch.setattr(lh, "portalocker", None)
    lh.write_text(p, "world\n")
    assert "world" in p.read_text(encoding="utf-8")


def test_write_json_fallback(tmp_path):
    """write_json deve serializar com fallback para objetos não JSON-serializáveis."""
    from src.system.log_helpers import write_json

    p = tmp_path / "j.jsonl"
    # sets are not JSON serializable; write_json should fallback using str
    write_json(p, {"x": {1, 2}})
    content = p.read_text(encoding="utf-8")
    assert "set(" in content or "{1, 2}" in content


def test_atomic_move_and_compress(tmp_path):
    """atomic_move_to_archive e compress_file devem mover e comprimir arquivos."""
    from src.system.log_helpers import atomic_move_to_archive, compress_file, is_older_than

    src = tmp_path / "src.txt"
    src.write_text("payload")
    dst_rot = tmp_path / "archive" / (src.name + ".rotating")

    # Should be able to move
    ok = atomic_move_to_archive(src, dst_rot)
    assert ok
    assert dst_rot.exists()

    # Create a file to compress
    src2 = tmp_path / "data.txt"
    src2.write_text("abc")
    gz = tmp_path / "out" / "data.txt.gz"
    ok2 = compress_file(src2, gz)
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
    assert is_older_than(older, 10)
