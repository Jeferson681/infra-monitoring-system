import pytest

from infra_monitoring.infra.system import time_helpers as th


def test_dfs_scan_and_localized_keys():
    """_extract_epoch deve localizar timestamps em estruturas aninhadas."""
    obj = {
        "meta": {"created_at": "2020-01-01T00:00:00Z"},
        "payload": [{"ts": "2020-02-02T00:00:00Z"}, {"other": "no"}],
    }
    val = th.extract_epoch(obj)
    assert isinstance(val, float)
    assert int(val) >= 1577836800

    # localized key
    obj2 = {"Data/hora": "2020-03-03T00:00:00Z"}
    localized = th._check_localized_date_keys(obj2)
    assert isinstance(localized, float)
    assert int(localized) >= 1583193600


def test_scan_list_for_keys_prefers_latest():
    """_scan_list_for_keys deve preferir a entrada mais recente na lista."""
    lst = [{"ts": "2020-01-01T00:00:00Z"}, {"ts": "2021-01-01T00:00:00Z"}]
    v = th._scan_list_for_keys(lst, 3)
    assert isinstance(v, float)
    assert int(v) >= 1609459200


def test_parse_date_string_formats():
    """_parse_date_string deve suportar epoch strings e ISO; valores inválidos retornam None."""
    assert th._parse_date_string("1609459200") == pytest.approx(1609459200)
    assert isinstance(th._parse_date_string("2020-01-01T00:00:00"), float)
    assert th._parse_date_string("bad") is None


def test_epoch_from_numeric_large_and_small():
    """_epoch_from_numeric converte milissegundo->segundo e passa por valores em segundos."""
    assert th._epoch_from_numeric(1609459200000) == pytest.approx(1609459200)
    assert th._epoch_from_numeric(1609459200) == pytest.approx(1609459200)
