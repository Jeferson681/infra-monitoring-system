import importlib

mod = importlib.import_module("src.system.helpers")


def test_validate_host_port():
    """Teste para validar host e porta."""
    assert mod.validate_host_port("127.0.0.1", 80)
    assert not mod.validate_host_port("", -1)


def test_read_env_file_missing(tmp_path):
    """Teste para leitura de arquivo .env que está faltando."""
    p = tmp_path / "nope.env"
    # should not raise, returns dict
    res = mod.read_env_file(p)
    assert isinstance(res, dict)


def test_merge_env_items(tmp_path, monkeypatch):
    """Teste para mesclar itens de ambiente."""
    # create env file
    f = tmp_path / ".env"
    f.write_text("A=1\nB=2")
    env = {"A": "override", "C": "3"}
    merged = mod.merge_env_items(f, env)
    # merged keys include A,B,C
    assert merged.get("A") == "override"
    assert merged.get("B") == "2"
    assert merged.get("C") == "3"
