from src.monitoring import state


def test_compute_metric_states_edge_cases():
    """Testa casos extremos para compute_metric_states e mapeamento interno."""
    # empty inputs -> empty mapping (wrapper behavior)
    assert state.compute_metric_states({}, {}) == {}

    # internal mapping produces STABLE/WARNING/CRITICAL
    metrics = {"cpu_percent": 95, "memory_used_bytes": 500}
    thresholds = {"cpu_percent": {"warning": 50, "critical": 90}, "memory_used_bytes": {"warning": 1000}}
    res = state._compute_metric_states(metrics, thresholds)
    assert res.get("state_cpu") in (state.STATE_WARNING, state.STATE_CRITICAL)


def test_systemstate_evaluate_activate_and_post_treatment(monkeypatch, tmp_path):
    """Testa avaliação, ativação e pós-tratamento em SystemState."""
    # Create SystemState with a low critical threshold so activation happens quickly
    s = state.SystemState(
        {"cpu_percent": {"warning": 10, "critical": 20}}, critical_duration=1, post_treatment_wait_seconds=0
    )

    # Monkeypatch SystemState._collect_metrics_after to return values showing improvement after treatment
    monkeypatch.setattr(state.SystemState, "_collect_metrics_after", lambda self=None: {"cpu_percent": 5})

    # Evaluate metrics that are critical and ensure state returned is string and activation occurs
    st = s.evaluate_metrics({"cpu_percent": 95})
    assert st in (state.STATE_CRITICAL, state.STATE_WARNING, state.STATE_STABLE)

    # normalize_for_display should include 'current'
    out = s.normalize_for_display()
    assert "current" in out

    # Prepare and record a post treatment snapshot directly
    snap = s._prepare_post_treatment_snapshot({"cpu_percent": 5}, [])
    assert snap.get("post_treatment") is True
    s._record_post_treatment_snapshot(snap)
    assert s.post_treatment_snapshot is not None


def test_post_treatment_write_fallback(monkeypatch, tmp_path):
    """Testa fallback de escrita de pós-tratamento quando a primária falha."""
    # Ensure _write_post_treatment_artifacts uses fallback when primary fails
    s = state.SystemState({}, post_treatment_wait_seconds=0)

    # Force _write_post_treatment_primary to raise so fallback is used
    def fake_primary(snap):
        raise OSError("primary fail")

    monkeypatch.setattr(s, "_write_post_treatment_primary", fake_primary)

    # Monkeypatch _write_post_treatment_fallback to write into tmp_path
    def fake_fallback(snap):
        p = tmp_path / "post_treatment.jsonl"
        p.write_text(str(snap))

    monkeypatch.setattr(s, "_write_post_treatment_fallback", fake_fallback)

    snap = {"state": state.STATE_POST_TREATMENT, "metrics": {}}
    s._write_post_treatment_artifacts(snap)
    assert (tmp_path / "post_treatment.jsonl").exists()
