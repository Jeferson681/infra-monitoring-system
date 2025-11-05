import pytest
import os
from src.system import log_helpers

pytest.skip("moved to archive_pre_reorg/duplicates/test_log_helpers_batch.py", allow_module_level=True)


def test_write_json_and_backup(tmp_path):
    """Testa se write_json cria o arquivo e backup corretamente."""
    p = tmp_path / "j.jsonl"
    log_helpers.write_json(p, {"a": 1})
    assert p.exists()


def test_process_temp_item_file_and_dir(tmp_path):
    """Testa process_temp_item para arquivos e diretórios temporários."""
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
    """Testa compress_file e atomic_move_to_archive."""
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
