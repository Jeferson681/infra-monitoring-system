import os
import time

from src.system import log_helpers
from src.system import logs


def test_sanitize_and_format():
    """Sanitization and date formatting helpers behave as expected."""
    assert log_helpers.sanitize_log_name("../../etc/passwd") != "../../etc/passwd"
    assert isinstance(log_helpers.format_date_for_log(), str)


def test_write_and_rotate(tmp_path):
    """Write text and compress_file produce files on disk."""
    lp = logs.get_log_paths(root=tmp_path)
    p = lp.log_dir / "t.log"
    log_helpers.write_text(p, "hello\n")
    assert p.exists()

    # test compress_file
    src = tmp_path / "file.txt"
    src.write_text("x")
    dst = tmp_path / "file.txt.gz"
    assert log_helpers.compress_file(src, dst) is True
    assert dst.exists()


def test_try_rotate_and_compress(tmp_path):
    """rotate_logs performs rotation for old files into archive."""
    lp = logs.get_log_paths(root=tmp_path)
    # create a .log file older than threshold
    f = lp.log_dir / "old.log"
    f.write_text("old")
    past = time.time() - 3600 * 24 * 2
    os.utime(f, (past, past))
    logs.rotate_logs(day_secs=1, week_secs=2)
    # archive dir should now have files or rotating placeholder
    assert lp.archive_dir.exists()
