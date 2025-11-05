"""Unit tests for src.system.helpers.

These are smoke tests that validate parsing and merging of .env files and a
few other small helpers. They are intentionally minimal and platform-safe.
"""


def test_read_env_file_nonexistent(tmp_path):
    """read_env_file retorna mapping vazio para ficheiro inexistente."""
    from src.system.helpers import read_env_file

    p = tmp_path / "nope.env"
    assert not p.exists()
    assert read_env_file(p) == {}


def test_read_env_file_parsing(tmp_path):
    """read_env_file parses key/value pairs and ignores comments/bad lines."""
    from src.system.helpers import read_env_file

    p = tmp_path / "test.env"
    p.write_text(
        """
# comment line
FOO=bar
QUOTED="baz"
EMPTY=
BADLINE
""",
        encoding="utf-8",
    )
    res = read_env_file(p)
    assert res.get("FOO") == "bar"
    assert res.get("QUOTED") == "baz"
    assert res.get("EMPTY") == ""
    assert "BADLINE" not in res


def test_merge_env_items_precedence(tmp_path, monkeypatch):
    """merge_env_items sobrescreve valores do ficheiro com os do process_env."""
    from src.system.helpers import merge_env_items

    p = tmp_path / "envf.env"
    p.write_text("A=1\nB=fromfile\n", encoding="utf-8")
    process_env = {"B": "fromproc", "C": "3"}
    merged = merge_env_items(p, process_env)
    assert merged["A"] == "1"
    assert merged["B"] == "fromproc"
    assert merged["C"] == "3"


def test_validate_host_port():
    """validate_host_port valida pares host:port razoáveis."""
    from src.system.helpers import validate_host_port

    assert validate_host_port("127.0.0.1", 80)
    assert not validate_host_port("not-an-ip", 80)
    assert not validate_host_port("127.0.0.1", 0)
    assert not validate_host_port("127.0.0.1", 65536)


def test_disk_candidate_paths_smoke():
    """Smoke test para candidatos de disco (retorna lista com Path/str)."""
    from src.system.helpers import _disk_candidate_paths

    cand = _disk_candidate_paths()
    assert isinstance(cand, list)
    assert len(cand) >= 1
    # entries should be Path or str
    from pathlib import Path as P

    assert any(isinstance(c, (P, str)) for c in cand)


def test_reap_children_nonblocking_smoke():
    """Smoke test para reap_children_nonblocking (deve ser seguro em todas as plataformas)."""
    from src.system.helpers import reap_children_nonblocking

    # This is a smoke test: ensure the call is safe on all platforms and returns a list
    res = reap_children_nonblocking()
    assert isinstance(res, list)


def test_import_helpers():
    """Importa o módulo de helpers do sistema sem erros."""
    import src.system.helpers as helpers

    assert helpers is not None
