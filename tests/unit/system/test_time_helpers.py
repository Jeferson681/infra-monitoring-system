from datetime import UTC, datetime

import pytest


def test_parse_epoch_numeric_and_iso():
    """_parse_epoch_from_value deve retornar float preciso e _parse_date_string parsear ISO."""
    from infra_monitoring.infra.system.time_helpers import (
        _parse_date_string,
        _parse_epoch_from_value,
    )

    num = _parse_epoch_from_value(1234567890)
    assert isinstance(num, float)
    assert num == pytest.approx(1234567890.0)

    iso = _parse_date_string("2020-01-02T03:04:05Z")
    assert isinstance(iso, float) and iso > 0

    assert _parse_date_string("notadate") is None


def test_extract_epoch_from_obj():
    """extract_epoch should find timestamps in common locations and return floats."""
    from infra_monitoring.infra.system.time_helpers import extract_epoch

    obj = {"ts": "2020-01-02T00:00:00Z"}
    val = extract_epoch(obj)
    assert isinstance(val, float)
    assert int(val) == 1577923200

    obj2 = {"metrics_raw": {"timestamp": "1600000000"}}
    val2 = extract_epoch(obj2)
    assert isinstance(val2, float)
    assert val2 == pytest.approx(1600000000.0)


def test_extract_epoch_from_datetime():
    """extract_epoch deve retornar epoch correto de datetime com timezone."""
    from infra_monitoring.infra.system.time_helpers import extract_epoch

    dt = datetime(2025, 10, 15, 12, 0, tzinfo=UTC)
    # extract_epoch expects a dict-like object; provide top-level 'ts'
    got = extract_epoch({"ts": dt.isoformat()})
    assert isinstance(got, float)
    assert int(got) == int(dt.timestamp())


def test_extract_epoch_from_timestamp():
    """extract_epoch aceita timestamps numéricos dentro de dicts e retorna float."""
    from infra_monitoring.infra.system.time_helpers import extract_epoch

    ts = 1600000000
    val = extract_epoch({"ts": ts})
    assert isinstance(val, float)
    assert val == float(ts)
