import gzip
import os
import time
from datetime import datetime


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


def test_ensure_dir_writable(tmp_path):
    """ensure_dir_writable cria diretório e permite escrita."""
    from src.system.log_helpers import ensure_dir_writable

    d = tmp_path / "subdir"
    assert ensure_dir_writable(d)
    # file created should be deletable by the function itself
    assert d.exists()


def test_sanitize_log_name_basic():
    """sanitize_log_name deve limpar nomes perigosos."""
    from src.system.log_helpers import sanitize_log_name

    assert sanitize_log_name("normal-name.log") == "normal-name.log"
    # sanitize_log_name keeps only the basename and replaces unsafe chars
    assert sanitize_log_name("../../etc/passwd") == "passwd"


def test_build_human_line_legacy_and_multiline(monkeypatch):
    """build_human_line deve alternar entre legacy e multiline."""
    from src.system.log_helpers import build_human_line

    ts = "2025-10-15T12:00:00Z"
    # Legacy mode off: when message has no internal newlines, we expect single-line
    monkeypatch.delenv("MONITORING_HUMAN_MULTILINE", raising=False)
    s0 = build_human_line(ts, "INFO", "hello world", extras={"a": 1})
    # legacy single-line should contain the message and only the trailing newline
    assert "hello world" in s0 and s0.rstrip("\n") == s0[:-1]

    # When message contains newlines, the function prefers multiline even if env var is unset
    s = build_human_line(ts, "INFO", "hello\nworld", extras={"a": 1})
    assert s.count("\n") >= 2

    # Multiline enabled
    monkeypatch.setenv("MONITORING_HUMAN_MULTILINE", "1")
    s2 = build_human_line(ts, "INFO", "hello\nworld", extras={"a": 1})
    assert s2.count("\n") >= 2


def test_normalize_message_for_human_and_truncate():
    """normalize_message_for_human remove novas linhas e trunca."""
    from src.system.log_helpers import normalize_message_for_human

    assert normalize_message_for_human(None) == ""
    assert normalize_message_for_human("long\nline").startswith("long")


def test_format_date_for_log():
    """format_date_for_log deve formatar objetos date/datetime corretamente."""
    from src.system.log_helpers import format_date_for_log

    d = datetime(2020, 1, 2)
    assert format_date_for_log(d) == "2020-01-02"


def test_is_older_than_and_ensure_dir_writable(tmp_path):
    """ensure_dir_writable cria pastas e is_older_than mede corretamente."""
    from src.system.log_helpers import is_older_than, ensure_dir_writable

    f = tmp_path / "t.txt"
    f.write_text("x")
    assert ensure_dir_writable(tmp_path)
    # Recent file should not be older than large seconds
    assert not is_older_than(f, 9999999)
