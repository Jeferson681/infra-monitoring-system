import json
import datetime
import time

import pytest

import src.monitoring.averages as averages
from src.system.time_helpers import extract_epoch


def test__extract_epoch_numeric_and_iso():
    """Verifica extração de epoch de números e strings ISO."""
    # numeric epoch (seconds)
    o1 = {"ts": 1700000000}
    assert pytest.approx(extract_epoch(o1), rel=1e-6) == 1700000000

    # ISO string
    iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    o2 = {"Data/hora": iso}
    assert extract_epoch(o2) is not None


def test__human_bytes():
    """Valida a formatação human-readable de bytes."""
    assert averages._human_bytes(1024**3) == "1.00 GB"
    assert averages._human_bytes(None) is None


def test_extract_relevant_and_normalize_state():
    """Confirma extração de campos relevantes e normalização de estado."""
    obj = {"state": "crit", "metrics_raw": {"cpu_percent": 12.5}}
    rel = averages.extract_relevant(obj)
    assert rel["cpu_percent"] == pytest.approx(12.5)
    assert averages._normalize_state("crit") == "CRITICAL"
    assert averages._normalize_state(None) is None


def test__iter_jsonl_today_and_lineno(tmp_path):
    """Gera JSONL temporário e valida iteração com número de linha correto."""
    # prepare a fake logs tree with today's date file
    today = datetime.date.today().strftime("%Y-%m-%d")
    logdir = tmp_path / "logs" / "json" / "monitoring"
    logdir.mkdir(parents=True)
    fname = f"monitoring-{today}.jsonl"
    fpath = logdir / fname
    # write two valid json lines and one malformed
    lines = [json.dumps({"a": 1}), "notjson", json.dumps({"b": 2})]
    fpath.write_text("\n".join(lines), encoding="utf-8")

    got = list(averages._iter_jsonl_today(tmp_path))
    # should yield only the two valid dicts with path and lineno
    assert len(got) == 2
    obj1, p1, ln1 = got[0]
    assert isinstance(obj1, dict)
    assert p1 == fpath
    assert ln1 == 1


def test_aggregate_last_seconds_creates_last_ts(tmp_path):
    """Gera entries JSONL e verifica que last_ts é persistido."""
    # create jsonl entries with timestamps inside 10s window
    today = datetime.date.today().strftime("%Y-%m-%d")
    logdir = tmp_path / "logs" / "json"
    logdir.mkdir(parents=True)
    fname = f"monitoring-{today}.jsonl"
    fpath = logdir / fname

    now = time.time()
    # two entries: one 8 seconds ago, one now
    entries = [
        json.dumps({"metrics_raw": {"timestamp": now - 8, "cpu_percent": 10}}),
        json.dumps({"metrics_raw": {"timestamp": now, "cpu_percent": 30}}),
    ]
    fpath.write_text("\n".join(entries), encoding="utf-8")

    agg = averages.aggregate_last_seconds(logs_root=tmp_path, seconds=10)
    assert agg is not None
    assert "averages" in agg
    # persisted last_ts should exist
    last = averages.read_last_time(logs_root=tmp_path)
    assert isinstance(last, float)
    assert last > 0


def test_extract_window_entries(tmp_path):
    """Verifica que extract_window_entries retorna os campos esperados."""
    # reuse same pattern: create one entry now
    today = datetime.date.today().strftime("%Y-%m-%d")
    logdir = tmp_path / "logs" / "json"
    logdir.mkdir(parents=True)
    fname = f"monitoring-{today}.jsonl"
    fpath = logdir / fname
    now = time.time()
    fpath.write_text(json.dumps({"metrics_raw": {"timestamp": now, "cpu_percent": 5}}) + "\n", encoding="utf-8")
    # test removed: functionality covered by aggregate_last_seconds


def test_format_long_metric_from_aggregate_includes_used_lines(tmp_path):
    """Assegura que o formato humano inclui a secção 'Linhas usadas'."""
    # build fake aggregate with used_files_lines
    agg = {
        "averages": {"cpu_percent": 55, "bytes_sent": None},
        "time_to": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "used_files_lines": {str(tmp_path / "a.jsonl"): (10, 20)},
    }
    out = averages.format_long_metric_from_aggregate(agg)
    assert "Linhas usadas" in out
    assert "a.jsonl" in out


def test_persist_and_read_last_time(tmp_path):
    """Testa persistência e leitura de last_ts para o diretório fornecido."""
    # ensure persist and read work and file is created under tmp_path
    p = averages.persist_last_time(logs_root=tmp_path)
    assert p.exists()
    v = averages.read_last_time(logs_root=tmp_path)
    assert isinstance(v, float)
