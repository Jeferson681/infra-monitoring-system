from pathlib import Path


from src.system import log_helpers as lh


def test_atomic_move_backoff_and_cleanup(tmp_path, monkeypatch):
    """Teste para backoff e limpeza em movimentação atômica."""
    # simulate rename/replace/copy all failing to exercise backoff and cleanup
    s = tmp_path / "s.txt"
    s.write_text("s")
    archive = tmp_path / "archive"
    archive.mkdir()
    dst = archive / (s.name + lh.ROTATING_SUFFIX)

    # Make all low-level operations raise
    monkeypatch.setattr(lh, "_attempt_rename", lambda a, b: False)
    monkeypatch.setattr(lh, "_attempt_replace", lambda a, b: False)
    monkeypatch.setattr(lh, "_copy_replace_fallback", lambda a, b: False)

    # Should return False and not raise
    assert lh.atomic_move_to_archive(s, dst) is False


def test_compress_file_error_path(tmp_path, monkeypatch):
    """Teste para erro de caminho na compressão de arquivo."""
    src = tmp_path / "f.txt"
    src.write_text("x")
    dst = tmp_path / "f.txt.gz"

    # monkeypatch gzip.open to raise OSError during write
    class BadGzip:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            raise OSError("gzip fail")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("gzip.open", BadGzip)

    # Should return False and not leave tmp files
    assert lh.compress_file(src, dst) is False


def test_format_extras_and_multiline_decision(monkeypatch):
    """Teste para decisão de multiline e formatação de extras."""
    extras = {"a": 1, "b": ["x", "y"]}
    s = lh._format_extras_for_human(extras)
    assert "a=1" in s and "b=" in s

    # multiline decision when env set
    monkeypatch.setenv("MONITORING_HUMAN_MULTILINE", "1")
    assert lh._should_use_multiline("hi") is True
    monkeypatch.setenv("MONITORING_HUMAN_MULTILINE", "0")
    assert lh._should_use_multiline("line1\nline2") is True


def test_is_older_than_oserror(monkeypatch, tmp_path):
    """Teste para OSError ao verificar se arquivo é antigo."""
    p = tmp_path / "nofile"

    # monkeypatch Path.stat to raise OSError
    class FakeStat:
        def __call__(self):
            raise OSError("no stat")

    monkeypatch.setattr(Path, "stat", lambda self: (_ for _ in ()).throw(OSError("stat fail")))

    assert lh.is_older_than(p, 10) is False


def test_format_date_for_log_various():
    """Teste para variações de formatação de data para log."""
    # None returns today's date string
    s = lh.format_date_for_log(None)
    assert isinstance(s, str) and len(s) >= 8

    # pass a date object
    from datetime import date, datetime

    d = date(2020, 1, 1)
    assert lh.format_date_for_log(d) == "2020-01-01"

    dt = datetime(2020, 2, 2, 3, 4, 5)
    assert lh.format_date_for_log(dt) == "2020-02-02"
