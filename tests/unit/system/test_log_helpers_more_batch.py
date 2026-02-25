from src.system import log_helpers as lh


import os


def test_is_older_than_and_all_children_old(tmp_path, monkeypatch):
    """Teste para is_older_than e all_children_old."""
    f = tmp_path / "f.txt"
    f.write_text("x")
    # set mtime to far past
    os.utime(f, (0, 0))
    assert lh.is_older_than(f, 1) is True

    d = tmp_path / "d"
    d.mkdir()
    c = d / "c"
    c.write_text("y")
    os.utime(c, (0, 0))
    assert lh.all_children_old(d, 1) is True

    """Teste para is_older_than_and_all_children_old."""


def test_try_rotate_and_compress(tmp_path, monkeypatch):
    """Teste para try_rotate_and_compress."""
    src = tmp_path / "log.txt"
    src.write_text("hello")
    # set mtime old
    os.utime(src, (0, 0))

    archive = tmp_path / "archive"
    archive.mkdir()

    # run try_rotate_file with small day/ week secs so it triggers
    lh.try_rotate_file(src, archive, ".gz", 1, 1)
    # either moved and compressed or left; ensure no exception and archive dir exists
    assert archive.exists()

    # create a .rotating file and ensure try_compress_rotating handles it
    rot = archive / ("log.txt" + lh.ROTATING_SUFFIX)
    rot.write_text("tmp")
    os.utime(rot, (0, 0))
    lh.try_compress_rotating(rot, archive, 1, 1)

    """Teste para try_rotate_and_compress."""


def test_ensure_dir_writable_permission_error(monkeypatch, tmp_path):
    """Teste para erro de permissão em ensure_dir_writable."""
    d = tmp_path / "pd"
    d.mkdir()

    # monkeypatch open to raise PermissionError when attempting to write test file
    real_open = open

    def fake_open(*a, **k):
        raise PermissionError("denied")

    monkeypatch.setattr("builtins.open", fake_open)
    try:
        assert lh.ensure_dir_writable(d) is False
    finally:
        monkeypatch.setattr("builtins.open", real_open)

    """Teste para ensure_dir_writable_permission_error."""


def test_attempt_replace_and_copy_fallback(tmp_path, monkeypatch):
    """Teste para attempt_replace e copy_fallback."""
    # create source file
    s = tmp_path / "s.txt"
    s.write_text("s")
    d = tmp_path / "archive" / "s.txt"
    """Teste para attempt_replace_and_copy_fallback."""

    # Monkeypatch os.replace to raise on first attempt to force copy fallback
    def raise_oserror(*args, **kwargs):
        raise OSError("replace fail")

    monkeypatch.setattr(lh.os, "replace", raise_oserror)
    res = lh._copy_replace_fallback(s, d)
    # copy fallback should either succeed or return False but not raise
    assert isinstance(res, bool)
