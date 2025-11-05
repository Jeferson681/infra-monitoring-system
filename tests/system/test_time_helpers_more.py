import pytest

from src.system import time_helpers as th


def test_dfs_scan_and_localized_keys():
    """Teste para a função de escaneamento DFS e chaves localizadas."""
    obj = {
        "meta": {"created_at": "2020-01-01T00:00:00Z"},
        "payload": [{"ts": "2020-02-02T00:00:00Z"}, {"other": "no"}],
    }
    val = th.extract_epoch(obj)
    assert val is not None

    # localized key
    obj2 = {"Data/hora": "2020-03-03T00:00:00Z"}
    assert th._check_localized_date_keys(obj2) is not None


def test_scan_list_for_keys_prefers_latest():
    """Teste para verificar se a lista de chaves prefere a mais recente."""
    lst = [{"ts": "2020-01-01T00:00:00Z"}, {"ts": "2021-01-01T00:00:00Z"}]
    v = th._scan_list_for_keys(lst, 3)
    assert v is not None
    assert int(v) >= 1609459200


def test_parse_date_string_formats():
    """Teste para formatos de string de data."""
    assert th._parse_date_string("1609459200") == pytest.approx(1609459200)
    assert th._parse_date_string("2020-01-01T00:00:00") is not None
    assert th._parse_date_string("bad") is None


def test_epoch_from_numeric_large_and_small():
    """Teste para conversão de epoch a partir de números grandes e pequenos."""
    assert th._epoch_from_numeric(1609459200000) == pytest.approx(1609459200)
    assert th._epoch_from_numeric(1609459200) == pytest.approx(1609459200)
