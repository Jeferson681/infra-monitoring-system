import gzip
from pathlib import Path


import pytest


def _write_text(path: Path, text: str):
    path.write_text(text, encoding="utf-8")


def _write_gzip(path: Path, text: str):
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(text)


def test_iter_jsonl_plain(tmp_path):
    """Plain JSONL with an invalid line and an empty line should yield valid items."""
    p = tmp_path / "data.jsonl"
    content = "{" + '"a": 1' + "}\n\ninvalid json\n{" + '"b": 2' + "}\n"
    _write_text(p, content)

    from src.system.ingest import iter_jsonl

    items = list(iter_jsonl(p))
    assert items == [{"a": 1}, {"b": 2}]


def test_iter_jsonl_gzip(tmp_path):
    """Gzipped JSONL should be decoded transparently."""
    p = tmp_path / "data.jsonl.gz"
    content = "{" + '"x": 10' + "}\n{" + '"y": 20' + "}\n"
    _write_gzip(p, content)

    from src.system.ingest import iter_jsonl

    items = list(iter_jsonl(p))
    assert items == [{"x": 10}, {"y": 20}]


def test_iter_jsonl_missing(tmp_path):
    """Missing file should raise FileNotFoundError immediately."""
    p = tmp_path / "does_not_exist.jsonl"
    from src.system.ingest import iter_jsonl

    with pytest.raises(FileNotFoundError):
        next(iter_jsonl(p))
