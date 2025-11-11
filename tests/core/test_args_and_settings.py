from types import SimpleNamespace
import pytest

from src.core import args as args_mod


def test_configure_argparser_defaults():
    """Teste para configuração de argumentos padrão do parser."""
    p = args_mod.configure_argparser()
    ns = p.parse_args([])
    assert ns.interval == 3.0
    assert ns.cycles == 1


def test_parse_args_and_validation():
    """Teste para parsing e validação de argumentos."""
    ns = args_mod.parse_args(["-i", "0.5", "-c", "2", "-v"])
    assert ns.interval == 0.5
    assert ns.cycles == 2
    assert ns.verbose == 1


def test_validate_args_errors():
    """Teste para validação de erros em argumentos."""
    ns = SimpleNamespace(interval="bad", cycles=1)
    with pytest.raises(ValueError):
        args_mod.validate_args(ns)
    ns2 = SimpleNamespace(interval=1.0, cycles=-1)
    with pytest.raises(ValueError):
        args_mod.validate_args(ns2)


def test_get_log_config_levels():
    """Teste para obtenção de níveis de configuração de log."""
    ns = SimpleNamespace(log_level="debug", log_root=None, verbose=0)
    cfg = args_mod.get_log_config(ns)
    assert cfg["level"] == "DEBUG"

    ns2 = SimpleNamespace(log_level=None, log_root=None, verbose=1)
    cfg2 = args_mod.get_log_config(ns2)
    assert cfg2["level"] == "INFO"

    ns3 = SimpleNamespace(log_level=None, log_root="/tmp", verbose=0)
    cfg3 = args_mod.get_log_config(ns3)
    assert cfg3["root"] == "/tmp"
