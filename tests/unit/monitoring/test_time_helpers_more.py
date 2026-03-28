import pytest

from infra_monitoring.infra.system import time_helpers


def test_epoch_from_numeric_and_parse():
    """_epoch_from_numeric and _parse_date_string handle common cases."""
    v = time_helpers._epoch_from_numeric(1650000000)
    assert isinstance(v, float) and v == pytest.approx(1650000000.0)
    pd = time_helpers._parse_date_string("2020-01-01T00:00:00Z")
    assert isinstance(pd, float)


def test_scan_and_extract_methods():
    """High-level extract_epoch finds timestamps in nested structures."""
    obj = {"metrics_raw": {"timestamp": "1600000000"}}
    v = time_helpers.extract_epoch(obj)
    assert isinstance(v, (int, float)) and int(v) == 1600000000

    obj2 = {"meta": {"time": "2020-01-01T00:00:00Z"}}
    v2 = time_helpers.extract_epoch(obj2)
    assert isinstance(v2, (int, float)) and int(v2) == 1577836800
