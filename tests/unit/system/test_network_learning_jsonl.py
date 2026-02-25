import json
import datetime
import pytest
from src.system.network_learning import NetworkUsageLearningHandler


def test_record_daily_usage_overwrites_and_appends(tmp_path):
    """Testa se record_daily_usage sobrescreve o dia atual e adiciona novo dia corretamente."""
    # Setup: use a temp cache file
    test_file = tmp_path / "network_usage_learning_safe.jsonl"
    handler = NetworkUsageLearningHandler()
    handler.LEARNING_FILE = test_file

    # Day 1: write initial value
    date1 = datetime.date(2025, 11, 13)
    handler.date_func = lambda: date1
    handler.record_daily_usage(100, 200)
    # Should have one entry
    lines = test_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry1 = json.loads(lines[0])
    assert entry1["bytes_sent"] == 100
    assert entry1["bytes_recv"] == 200
    assert entry1["date"] == "2025-11-13"
    assert "timestamp" in entry1

    # Day 1 again: overwrite with new value
    handler.record_daily_usage(300, 400)
    lines = test_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry1b = json.loads(lines[0])
    assert entry1b["bytes_sent"] == 300
    assert entry1b["bytes_recv"] == 400
    assert entry1b["date"] == "2025-11-13"
    assert "timestamp" in entry1b

    # Day 2: append new day
    date2 = datetime.date(2025, 11, 14)
    handler.date_func = lambda: date2
    handler.record_daily_usage(500, 600)
    lines = test_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    entry2 = json.loads(lines[1])
    assert entry2["bytes_sent"] == 500
    assert entry2["bytes_recv"] == 600
    assert entry2["date"] == "2025-11-14"
    assert "timestamp" in entry2

    # Day 2 again: overwrite with new value
    handler.record_daily_usage(700, 800)
    lines = test_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    entry2b = json.loads(lines[1])
    assert entry2b["bytes_sent"] == 700
    assert entry2b["bytes_recv"] == 800
    assert entry2b["date"] == "2025-11-14"
    assert "timestamp" in entry2b

    # Check order: first is day 1, second is day 2
    entry1_final = json.loads(lines[0])
    entry2_final = json.loads(lines[1])
    assert entry1_final["date"] == "2025-11-13"
    assert entry2_final["date"] == "2025-11-14"


if __name__ == "__main__":
    pytest.main([__file__])
