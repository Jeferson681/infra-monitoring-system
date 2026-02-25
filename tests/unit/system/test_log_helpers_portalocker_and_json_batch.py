from src.system import log_helpers as lh


def test_write_text_with_portalocker(monkeypatch, tmp_path):
    """Teste para escrita de texto usando portalocker."""
    p = tmp_path / "t.txt"

    class FakePL:
        LOCK_EX = 1

        @staticmethod
        def lock(fh, mode):
            return True

        @staticmethod
        def unlock(fh):
            return True

    monkeypatch.setattr(lh, "portalocker", FakePL, raising=False)
    monkeypatch.setattr(lh, "DURABLE_WRITES", False, raising=False)
    lh.write_text(p, "hello\n")
    assert p.exists()


def test_write_text_fsync_failure(monkeypatch, tmp_path):
    """Teste para falha de fsync na escrita de texto."""
    p = tmp_path / "t2.txt"

    # force DURABLE_WRITES true and make fsync raise
    monkeypatch.setattr(lh, "DURABLE_WRITES", True, raising=False)

    def raise_oserror(*args, **kwargs):
        raise OSError("fsync fail")

    monkeypatch.setattr(lh.os, "fsync", raise_oserror)
    # no exception should be raised
    lh.write_text(p, "x\n")
    assert p.exists()


def test_write_json_fallback_default_str(monkeypatch, tmp_path):
    """Teste para fallback de write_json usando str padrão."""
    p = tmp_path / "j.jsonl"

    class Bad:
        def __init__(self):
            self.x = object()

    # make json.dumps raise TypeError the first time by monkeypatching _json.dumps
    real_dumps = lh._json.dumps

    def fake_dumps(obj, **k):
        # raise TypeError only on first attempt for Bad to trigger fallback
        if isinstance(obj, Bad) and not getattr(fake_dumps, "_called", False):
            fake_dumps._called = True
            raise TypeError("no")
        return real_dumps(obj, **k)

    monkeypatch.setattr(lh._json, "dumps", fake_dumps)
    # Should not raise
    lh.write_json(p, {"bad": lambda x: x})
    assert p.exists()


def test_build_human_line_multiline_env(monkeypatch):
    """Teste para multiline em build_human_line via env."""
    monkeypatch.setenv("MONITORING_HUMAN_MULTILINE", "1")
    s = lh.build_human_line("ts", "INFO", "line1\nline2", {"a": 1})
    assert "\n" in s
