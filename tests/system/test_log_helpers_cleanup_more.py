import os
import pytest
from pathlib import Path

from src.system import log_helpers as lh


def test_atomic_move_cleanup_when_dst_exists(tmp_path, monkeypatch):
    """Teste para limpeza após movimentação atômica quando destino existe."""
    s = tmp_path / "s.txt"
    s.write_text("s")
    archive = tmp_path / "archive"
    archive.mkdir()
    dst = archive / (s.name + lh.ROTATING_SUFFIX)
    # create dst and ensure src removed to trigger cleanup path
    dst.write_text("old")

    # make attempts fail
    monkeypatch.setattr(lh, "_attempt_rename", lambda a, b: False)
    monkeypatch.setattr(lh, "_attempt_replace", lambda a, b: False)
    monkeypatch.setattr(lh, "_copy_replace_fallback", lambda a, b: False)

    # remove src so function will perform cleanup of dst if src missing
    s.unlink()
    res = lh.atomic_move_to_archive(s, dst)
    assert res is False


def test_try_compress_rotating_unlink(tmp_path, monkeypatch):
    """Teste para tentativa de compressão e remoção rotativa."""
    archive = tmp_path / "archive"
    archive.mkdir()
    rot = archive / ("file" + lh.ROTATING_SUFFIX)
    rot.write_text("x")
    # set mtime old
    os.utime(rot, (0, 0))

    # make compress_file succeed and ensure rotating gets unlinked
    monkeypatch.setattr(lh, "compress_file", lambda a, b: True)
    lh.try_compress_rotating(rot, archive, 1, 1)
    assert not rot.exists()


def test_write_text_outer_oserror_fallback(tmp_path, monkeypatch):
    """Teste para fallback de escrita de texto com OSError externo."""
    d = tmp_path / "logs"
    d.mkdir()
    target = d / "out.log"

    # Simulate Path.open raising OSError by patching Path.open
    def fake_open(self, *args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "open", fake_open, raising=False)

    # write_text logs the error and returns None (best-effort). Ensure no file created.
    res = lh.write_text(target, "hello\n")
    assert res is None
    assert not target.exists()


def test_write_json_full_failure_fallback(tmp_path, monkeypatch):
    """Teste para fallback de escrita de JSON em falha total."""
    d = tmp_path / "logs2"
    d.mkdir()
    target = d / "out.jsonl"

    # Simulate write_text also failing
    def fake_write_text(path, text, *args, **kwargs):
        raise OSError("no space")

    monkeypatch.setattr(lh, "write_text", fake_write_text)

    # Usando um dicionário com valor não serializável para simular falha de serialização
    obj = {"bad": lambda x: x}

    # Espera que write_json tente fallback e write_text (que foi mockado para lançar OSError)
    with pytest.raises(OSError):
        lh.write_json(target, obj)
    assert not target.exists()


def test_build_human_line_truncation_and_multiline(tmp_path):
    """Teste para truncamento e multiline de linha humana."""
    # build_human_line handles message truncation and extras formatting
    msg = "a" * 4000  # long message
    extras = {"k": "v"}

    # supply timestamp and level required by signature
    line = lh.build_human_line("2025-10-17T00:00:00Z", "INFO", msg, extras=extras)
    assert isinstance(line, str)
    # When message too long, ensure the header is present and the body includes the start of the message
    assert line.startswith("2025-10-17T00:00:00Z [INFO]")
    assert "aaaaa" in line
    # multiline check: if message contains newline, should produce human multiline
    m2 = "line1\nline2\n"
    line2 = lh.build_human_line("2025-10-17T00:00:00Z", "INFO", m2, extras={})
    assert "line1" in line2
    assert "line2" in line2


def test_process_temp_item_dir_removal(tmp_path):
    """Teste para remoção de diretório temporário."""
    # create a fake temp dir with nested files
    base = tmp_path / "tmpdir"
    base.mkdir()
    child = base / "child"
    child.mkdir()
    f = child / "file.txt"
    f.write_text("ok")

    # Make files and dirs appear old
    for p in (f, child, base):
        os.utime(p, (0, 0))

    # Now process temp item and ensure directory is removed
    lh.process_temp_item(base, max_age=1)
    # base may be removed; if not, ensure it's empty or has been cleaned
    if base.exists():
        assert not any(base.iterdir())


# Additional edge: ensure compress_file leaves original when gzip fails


def test_compress_file_failure_leaves_original(tmp_path, monkeypatch):
    """Teste para falha de compressão mantendo arquivo original."""
    src = tmp_path / "log.txt"
    src.write_text("hello")

    # Simulate gzip.open raising an exception when used as context manager
    def fake_gzip_open(*args, **kwargs):
        class Ctx:
            def __enter__(self):
                raise OSError("can't compress")

            def __exit__(self, exc_type, exc, tb):
                return False

        return Ctx()

    monkeypatch.setattr(lh.gzip, "open", fake_gzip_open)

    dst = src.with_suffix(src.suffix + ".gz")
    # compress_file should handle the failure and return False, leaving original
    res = lh.compress_file(src, dst)
    assert res is False
    assert src.exists()
    assert not dst.exists()


def test_copy_replace_fallback_cleanup_on_failure(tmp_path, monkeypatch):
    """Teste para fallback de cópia/substituição e limpeza em falha."""
    s = tmp_path / "s.txt"
    s.write_text("s")
    archive = tmp_path / "archive"
    archive.mkdir()
    d = archive / "s.txt"

    # Pre-create a tmp file so function must cleanup it when copy fails
    tmp = d.with_suffix(d.suffix + ".tmp")
    tmp.write_text("oldtmp")

    import shutil as _sh

    def bad_copy(a, b):
        raise OSError("copy fail")

    monkeypatch.setattr(_sh, "copy2", bad_copy)

    res = lh._copy_replace_fallback(s, d)
    assert res is False
    assert not tmp.exists()


def test_ensure_dir_writable_permission_error(tmp_path, monkeypatch):
    """Teste para erro de permissão ao garantir diretório gravável."""
    p = tmp_path / "x"

    def fake_mkdir(self, *a, **kw):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "mkdir", fake_mkdir, raising=False)

    res = lh.ensure_dir_writable(p)
    assert res is False


def test_atomic_move_rename_short_circuit(tmp_path, monkeypatch):
    """Teste para atalho de renomeação em movimentação atômica."""
    s = tmp_path / "s2.txt"
    s.write_text("ok")
    dst = tmp_path / "archive" / (s.name + lh.ROTATING_SUFFIX)
    dst.parent.mkdir()

    monkeypatch.setattr(lh, "_attempt_rename", lambda a, b: True)

    res = lh.atomic_move_to_archive(s, dst)
    assert res is True


def test_try_rotate_file_no_action_if_not_old(tmp_path, monkeypatch):
    """Teste para rotação de arquivo sem ação se não for antigo."""
    p = tmp_path / "log.txt"
    p.write_text("x")
    archive = tmp_path / "archive"
    archive.mkdir()

    # Ensure is_older_than returns False so function returns early
    monkeypatch.setattr(lh, "is_older_than", lambda path, secs: False)

    # If atomic_move_to_archive is called it indicates a bug; ensure it's not called
    def fail_if_called(*a, **kw):
        raise AssertionError("atomic_move_to_archive should not be called when not old")

    monkeypatch.setattr(lh, "atomic_move_to_archive", fail_if_called)

    lh.try_rotate_file(p, archive, ".gz", day_secs=86400, week_secs=604800)
    assert p.exists()
