from src.system import time_helpers


def test_epoch_from_numeric_and_parse():
    """_epoch_from_numeric and _parse_date_string handle common cases."""
    assert time_helpers._epoch_from_numeric(1650000000) == 1650000000.0
    assert isinstance(time_helpers._parse_date_string("2020-01-01T00:00:00Z"), float)


def test_scan_and_extract_methods():
    """High-level extract_epoch finds timestamps in nested structures."""
    obj = {"metrics_raw": {"timestamp": "1600000000"}}
    v = time_helpers.extract_epoch(obj)
    assert v is not None and int(v) == 1600000000

    obj2 = {"meta": {"time": "2020-01-01T00:00:00Z"}}
    v2 = time_helpers.extract_epoch(obj2)
    assert v2 is not None and int(v2) == 1577836800
