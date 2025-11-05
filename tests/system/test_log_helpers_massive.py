import os
from pathlib import Path

from src.system import log_helpers as lh


def test_sanitize_log_name_and_long_name():
    """Teste para sanitização de nome de log e nome longo."""
    assert lh.sanitize_log_name("..weird/name!!") != ""
    long = "a" * 500
    s = lh.sanitize_log_name(long)
    assert len(s) <= 200


def test_normalize_message_for_human_handles_exceptions(monkeypatch):
    """Teste para normalização de mensagem para humano lidando com exceções."""

    class Bad:
        def __str__(self):
            raise ValueError("bad")

    assert lh.normalize_message_for_human(Bad()) == "<unrepr>"


def test_build_json_entry_merges_extras():
    """Teste para build_json_entry mesclando extras."""
    e = lh.build_json_entry("ts", "INFO", "m", {"a": 1})
    assert e["ts"] == "ts"
    assert e["a"] == 1


def test_is_older_than_oserror(tmp_path, monkeypatch):
    """Teste para OSError em is_older_than."""
    p = tmp_path / "nofile"

    # stat raises OSError
    def fake_stat():
        raise OSError("boom")

    monkeypatch.setattr(Path, "stat", lambda self: (_ for _ in ()).throw(OSError("boom")))
    assert lh.is_older_than(p, 10) is False


def test_archive_file_is_old_oserror(tmp_path, monkeypatch):
    """Teste para OSError em archive_file_is_old."""
    p = tmp_path / "x"
    monkeypatch.setattr(Path, "stat", lambda self: (_ for _ in ()).throw(OSError("boom")))
    assert lh.archive_file_is_old(p, 0, 1) is False


def test_attempts_failures(tmp_path, monkeypatch):
    """Teste para falhas de tentativas de rename/replace/copy."""
    s = tmp_path / "s.txt"
    s.write_text("x")
    d = tmp_path / "d.txt"

    # force rename and replace to fail
    monkeypatch.setattr(lh, "_attempt_rename", lambda a, b: False)
    monkeypatch.setattr(lh, "_attempt_replace", lambda a, b: False)

    # patch shutil.copy2 to raise
    import shutil as _sh

    monkeypatch.setattr(_sh, "copy2", lambda a, b: (_ for _ in ()).throw(OSError("boom")))

    res = lh._copy_replace_fallback(s, d)
    assert res is False


def test_all_children_old_oserror(tmp_path, monkeypatch):
    """Teste para OSError em all_children_old."""
    d = tmp_path / "d"
    d.mkdir()

    monkeypatch.setattr(Path, "iterdir", lambda self: (_ for _ in ()).throw(OSError("boom")))
    assert lh.all_children_old(d, 1) is False


def test_process_temp_item_file_unlink(tmp_path, monkeypatch):
    """Teste para falha de unlink em process_temp_item."""
    f = tmp_path / "a.txt"
    f.write_text("x")
    os.utime(f, (0, 0))
    # simulate unlink raising
    monkeypatch.setattr(Path, "unlink", lambda self, missing_ok=False: (_ for _ in ()).throw(OSError("boom")))
    # should not raise
    lh.process_temp_item(f, max_age=1)


def test_format_date_for_log_variants():
    """Teste para variantes de format_date_for_log."""
    assert isinstance(lh.format_date_for_log(), str)
    from datetime import datetime

    dt = datetime(2020, 1, 2)
    assert lh.format_date_for_log(dt) == "2020-01-02"


def test_should_use_multiline_env_and_contents(monkeypatch):
    """Teste para multiline via env e conteúdo."""
    monkeypatch.setenv("MONITORING_HUMAN_MULTILINE", "1")
    assert lh._should_use_multiline("no matter") is True
    monkeypatch.delenv("MONITORING_HUMAN_MULTILINE", raising=False)
    assert lh._should_use_multiline("a\nline") is True


def test_ensure_dir_writable_cleanup(tmp_path, monkeypatch):
    """Teste para cleanup em ensure_dir_writable."""
    p = tmp_path / "x"

    # simulate write failing then cleanup
    def fake_open(*a, **kw):
        raise PermissionError("denied")

    monkeypatch.setattr(lh, "open", fake_open, raising=False)
    res = lh.ensure_dir_writable(p)
    assert res is False


def test_compress_file_raises_and_cleans(tmp_path, monkeypatch):
    """Teste para compressão de arquivo que gera exceção e limpa arquivos temporários."""
    src = tmp_path / "src.txt"
    src.write_text("x")
    dst = tmp_path / "dst.gz"

    # simulate gzip.open raising inside context
    def fake_gzip_open(*a, **kw):
        class Ctx:
            def __enter__(self):
                raise OSError("boom")

            def __exit__(self, t, v, tb):
                return False

        return Ctx()

    monkeypatch.setattr(lh.gzip, "open", fake_gzip_open)
    res = lh.compress_file(src, dst)
    assert res is False
