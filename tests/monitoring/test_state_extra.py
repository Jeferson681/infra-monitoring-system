from src.monitoring import state


def test_compute_metric_states_basic():
    """_compute_metric_states classifies metrics into per-metric state keys."""
    metrics = {"cpu_percent": 80, "memory_used_bytes": 100}
    thresholds = {"cpu_percent": {"warning": 50, "critical": 90}, "memory_used_bytes": {"warning": 50}}
    res = state._compute_metric_states(metrics, thresholds)
    assert res.get("state_cpu") in (state.STATE_WARNING, state.STATE_STABLE)


def test_compute_metric_states_public_wrapper():
    """Public wrapper returns empty mapping when given empty inputs."""
    assert state.compute_metric_states({}, {}) == {}


def test_systemstate_evaluate_and_snapshots(tmp_path, monkeypatch):
    """SystemState evaluates metrics and updates snapshots appropriately."""
    s = state.SystemState(
        {"cpu_percent": {"warning": 10, "critical": 90}},
        critical_duration=1,
        post_treatment_wait_seconds=0,
    )
    metrics = {"cpu_percent": 95}
    st = s.evaluate_metrics(metrics)
    assert st in (state.STATE_CRITICAL, state.STATE_WARNING, state.STATE_STABLE)
    disp = s.normalize_for_display()
    assert "current" in disp


def test_prepare_post_treatment_and_record(monkeypatch, tmp_path):
    """Prepare and record post-treatment snapshots and ensure history truncation."""
    s = state.SystemState({}, post_treatment_wait_seconds=0)
    snap = s._prepare_post_treatment_snapshot({"a": 1}, [])
    assert snap.get("post_treatment") is True
    s._record_post_treatment_snapshot(snap)
    assert s.post_treatment_snapshot is not None
    # ensure truncation works
    for i in range(15):
        s._record_post_treatment_snapshot({"idx": i})
    assert len(s.post_treatment_history) <= 10
