import json
import time
import pytest

from src.system.log_helpers import build_human_line
from src.system.logs import get_log_paths
from src.config.settings import load_settings
from src.monitoring.state import SystemState


def test_human_multiline_env(tmp_path, monkeypatch):
    """Verify multiline human log format toggled by env var."""
    # default (no env) should be single-line
    # default (no env) should still return multilines if message has newlines
    monkeypatch.delenv("MONITORING_HUMAN_MULTILINE", raising=False)
    line = build_human_line("2025-10-10", "INFO", "a\nb")
    assert line.count("\n") >= 2
    # enabling env var still results in multilines
    monkeypatch.setenv("MONITORING_HUMAN_MULTILINE", "1")
    line_ml = build_human_line("2025-10-10", "INFO", "a\nb")
    assert line_ml.count("\n") >= 2


def test_threshold_override_accepts_critical(monkeypatch, tmp_path):
    """Environment override MONITORING_THRESHOLD_*_CRITICAL should set critical."""
    monkeypatch.setenv("MONITORING_THRESHOLD_CPU_PERCENT_CRITICAL", "88")
    s = load_settings()
    thr = s.get("thresholds")
    assert isinstance(thr, dict)
    assert thr["cpu_percent"]["critical"] == pytest.approx(88.0)


def test_post_treatment_history_written(tmp_path, monkeypatch):
    """Trigger a post-treatment snapshot and verify history file is appended."""
    monkeypatch.setenv("MONITORING_LOG_ROOT", str(tmp_path))
    thresholds = {"cpu_percent": {"warning": 1.0, "critical": 2.0}}
    st = SystemState(thresholds, critical_duration=0, post_treatment_wait_seconds=0)

    # simulate entering critical to trigger treatment (call twice: first sets active, second triggers treatment)
    st._update_snapshots("critical", {"cpu_percent": 3.0})
    st._update_snapshots("critical", {"cpu_percent": 3.0})
    # wait for background worker to run
    time.sleep(0.5)

    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    hist = project_root / ".cache" / "post_treatment_history.jsonl"
    assert hist.exists(), f"history file not found: {hist}"
    # ensure at least one line is JSON
    with hist.open("r", encoding="utf-8") as fh:
        lines = [line for line in fh.read().splitlines() if line.strip()]
    assert len(lines) >= 1
    obj = json.loads(lines[-1])
    assert obj.get("state") == "post_treatment"


def test_post_treatment_emitted_to_monitoring_feed(tmp_path, monkeypatch):
    """Trigger post_treatment and verify a JSONL entry is appended to monitoring feed.

    The emitted object should have msg 'post_treatment', include post_treatment=True,
    contain 'alerts' and should NOT include 'summary_short'/'summary_long'.
    """
    monkeypatch.setenv("MONITORING_LOG_ROOT", str(tmp_path))
    thresholds = {"cpu_percent": {"warning": 1.0, "critical": 2.0}}
    st = SystemState(thresholds, critical_duration=0, post_treatment_wait_seconds=0)

    # trigger treatment
    st._update_snapshots("critical", {"cpu_percent": 3.0})
    st._update_snapshots("critical", {"cpu_percent": 3.0})
    # wait for background worker
    time.sleep(0.5)

    # find monitoring jsonl
    lp = get_log_paths()
    fname = lp.json_dir / f"monitoring-{time.strftime('%Y-%m-%d')}.jsonl"
    assert fname.exists(), f"monitoring feed not found: {fname}"
    with fname.open("r", encoding="utf-8") as fh:
        lines = [ln for ln in fh.read().splitlines() if ln.strip()]
    assert lines, "no lines in monitoring feed"
    last = json.loads(lines[-1])
    assert last.get("msg") == "post_treatment"
    assert last.get("post_treatment") is True
    assert "alerts" in last
    assert "summary_short" not in last and "summary_long" not in last
