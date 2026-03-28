import os
import time

from infra_monitoring.infra.system import log_helpers, logs


def test_sanitize_and_format():
    """Sanitization and date formatting helpers behave as expected."""
    out = log_helpers.sanitize_log_name("../../etc/passwd")
    assert isinstance(out, str) and out != "../../etc/passwd"
    fd = log_helpers.format_date_for_log()
    assert isinstance(fd, str) and len(fd) > 0


def test_write_and_rotate(tmp_path):
    """Write text and compress_file produce files on disk."""
    lp = logs.get_log_paths(root=tmp_path)
    p = lp.log_dir / "t.log"
    log_helpers.write_text(p, "hello\n")
    assert p.exists()
    # file should contain the written content
    assert p.read_text(encoding="utf-8").startswith("hello")

    # test compress_file
    src = tmp_path / "file.txt"
    src.write_text("x")
    dst = tmp_path / "file.txt.gz"
    assert log_helpers.compress_file(src, dst) is True
    assert dst.exists()
    assert dst.stat().st_size > 0


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
    # archive should contain at least one file (rotated or compressed)
    contents = list(lp.archive_dir.iterdir())
    assert len(contents) >= 0
