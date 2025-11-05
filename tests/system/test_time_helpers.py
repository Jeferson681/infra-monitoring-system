from datetime import datetime, timezone


def test_parse_epoch_numeric_and_iso():
    """_numeric and ISO string parsing produce epoch floats or None."""
    from src.system.time_helpers import _parse_epoch_from_value, _parse_date_string

    assert isinstance(_parse_epoch_from_value(1234567890), float)
    assert _parse_date_string("2020-01-02T03:04:05Z") is not None
    assert _parse_date_string("notadate") is None


def test_extract_epoch_from_obj():
    """extract_epoch should find timestamps in common locations."""
    from src.system.time_helpers import extract_epoch

    obj = {"ts": "2020-01-02T00:00:00Z"}
    val = extract_epoch(obj)
    assert val is not None and val > 0
    obj2 = {"metrics_raw": {"timestamp": "1600000000"}}
    val2 = extract_epoch(obj2)
    assert val2 is not None and val2 > 0


def test_extract_epoch_from_datetime():
    """extract_epoch deve retornar epoch correto de datetime com timezone."""
    from src.system.time_helpers import extract_epoch

    dt = datetime(2025, 10, 15, 12, 0, tzinfo=timezone.utc)
    # extract_epoch expects a dict-like object; provide top-level 'ts'
    got = extract_epoch({"ts": dt.isoformat()})
    assert got is not None
    assert int(got) == int(dt.timestamp())


def test_extract_epoch_from_timestamp():
    """extract_epoch aceita timestamps numéricos dentro de dicts."""
    from src.system.time_helpers import extract_epoch

    ts = 1600000000
    val = extract_epoch({"ts": ts})
    assert val is not None
    assert val == float(ts)
