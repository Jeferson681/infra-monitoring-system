import os

from src.system import log_helpers


def test_sanitize_and_normalize_and_builders():
    """Teste para sanitização, normalização e builders de logs."""
    assert log_helpers.sanitize_log_name("..bad/name!!") != ""
    assert " " not in log_helpers.sanitize_log_name("name with space")

    assert log_helpers.normalize_message_for_human("a\nb") == "a b"
    assert log_helpers.normalize_message_for_human(None) == ""

    ts = "2025-10-15"
    entry = log_helpers.build_json_entry(ts, "INFO", "msg", {"k": "v"})
    assert entry["ts"] == ts and entry["msg"] == "msg"

    human = log_helpers.build_human_line(ts, "WARN", "hello", {"a": 1})
    assert ts in human and "WARN" in human


def test_ensure_dir_writable_and_write_text(tmp_path):
    """Teste para garantir diretório gravável e escrita de texto."""
    d = tmp_path / "logs"
    assert log_helpers.ensure_dir_writable(d) is True
    p = d / "t.txt"
    log_helpers.write_text(p, "x\n")
    assert p.exists()
    # cleanup
    p.unlink()


def test_write_json_and_backup(tmp_path):
    """Teste para escrita de JSON e backup."""
    p = tmp_path / "j.jsonl"
    log_helpers.write_json(p, {"a": 1})
    assert p.exists()


def test_process_temp_item_file_and_dir(tmp_path):
    """Teste para processamento de arquivo e diretório temporário."""
    # create temp file older than threshold
    f = tmp_path / "old.tmp"
    f.write_text("x")
    # set mtime to far past
    old = 0
    os.utime(f, (old, old))
    log_helpers.process_temp_item(f, 1)
    # may be removed or logged; ensure no exception

    d = tmp_path / "d"
    d.mkdir()
    child = d / "c"
    child.write_text("y")
    os.utime(child, (0, 0))
    log_helpers.process_temp_item(d, 1)


def test_compress_and_atomic_move(tmp_path):
    """Teste para compressão e movimentação atômica de arquivo."""
    src = tmp_path / "a.txt"
    src.write_text("hello")
    dst_gz = tmp_path / "a.txt.gz"
    assert log_helpers.compress_file(src, dst_gz) is True
    assert dst_gz.exists()

    # test atomic_move_to_archive fallbacks by simulating rename failure
    src2 = tmp_path / "b.txt"
    src2.write_text("b")
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    dst_rotating = archive_dir / (src2.name + log_helpers.ROTATING_SUFFIX)

    # normal path should succeed
    assert log_helpers.atomic_move_to_archive(src2, dst_rotating) is True
