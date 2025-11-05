import gzip


def test_write_json_fallback(tmp_path):
    """write_json should serialize non-serializable objects with fallback."""
    from src.system.log_helpers import write_json

    p = tmp_path / "out.jsonl"
    # set is not JSON serializable by default
    write_json(p, {"a": {1, 2, 3}})
    content = p.read_text(encoding="utf-8")
    assert "a" in content


def test_write_text_with_portalocker(monkeypatch, tmp_path):
    """write_text should attempt to use portalocker when available."""
    import src.system.log_helpers as lh

    class DummyLock:
        def __init__(self):
            self.locked = False

        def lock(self, fh, mode):
            self.locked = True

        def unlock(self, fh):
            self.locked = False

    monkeypatch.setattr(lh, "portalocker", DummyLock())
    p = tmp_path / "f.txt"
    # Should not raise
    lh.write_text(p, "hello")
    assert p.read_text(encoding="utf-8").startswith("hello")


def test_build_json_entry_and_format_extras():
    """build_json_entry and _format_extras_for_human produce expected outputs."""
    from src.system.log_helpers import build_json_entry, _format_extras_for_human

    e = build_json_entry("t", "INFO", "msg", extra={"k": "v"})
    assert e["ts"] == "t" and e["level"] == "INFO"
    s = _format_extras_for_human({"k": "v", "list": [1, 2]})
    assert "k=v" in s and "list=" in s


def test_atomic_move_and_compress(tmp_path):
    """atomic_move_to_archive and compress_file should move and compress files."""
    from src.system.log_helpers import atomic_move_to_archive, compress_file, ROTATING_SUFFIX

    src = tmp_path / "log.txt"
    src.write_text("hello")
    archive = tmp_path / "archive"
    archive.mkdir()
    dst_rotating = archive / (src.name + ROTATING_SUFFIX)

    moved = atomic_move_to_archive(src, dst_rotating)
    assert moved
    # create a small file to compress
    r = archive / "small.txt"
    r.write_text("x")
    gz = archive / "small.txt.gz"
    compressed = compress_file(r, gz)
    assert compressed
    assert gz.exists()
    # gzip should be readable
    with gzip.open(gz, "rt", encoding="utf-8") as fh:
        assert fh.read().strip() == "x"
