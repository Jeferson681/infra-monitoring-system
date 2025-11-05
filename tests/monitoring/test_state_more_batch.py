from src.monitoring import state as s


def test_compute_metric_states_empty():
    """Testa compute_metric_states com entradas vazias."""
    assert s.compute_metric_states({}, {}) == {}


def test_compute_metric_states_thresholds():
    """Testa compute_metric_states com thresholds de warning."""
    metrics = {"cpu_percent": 80, "memory_used_bytes": 500}
    thresholds = {"cpu_percent": {"warning": 50, "critical": 90}, "memory_used_bytes": {"warning": 400}}
    out = s.compute_metric_states(metrics, thresholds)
    assert out["state_cpu"] == s.STATE_WARNING
    assert out["state_ram"] == s.STATE_WARNING


def test_systemstate_evaluate_and_snapshot(monkeypatch, tmp_path):
    """Testa avaliação e snapshot em SystemState."""
    thr = {"cpu_percent": {"warning": 50, "critical": 75}}
    ss = s.SystemState(thr, critical_duration=1, post_treatment_wait_seconds=0)

    # Evaluate stable
    state = ss.evaluate_metrics({"cpu_percent": 10})
    assert state == s.STATE_STABLE
    norm = ss.normalize_for_display()
    assert "current" in norm

    # Evaluate warning
    state = ss.evaluate_metrics({"cpu_percent": 60})
    assert state == s.STATE_WARNING


def test_activation_and_post_treatment(monkeypatch, tmp_path):
    """Testa ativação e pós-tratamento em SystemState."""
    # create SystemState with tiny sustained_crit_seconds so activation triggers
    thr = {"cpu_percent": {"warning": 50, "critical": 10}}
    ss = s.SystemState(thr, critical_duration=0, post_treatment_wait_seconds=0)

    # monkeypatch _collect_metrics_after to return some metrics
    monkeypatch.setattr(ss, "_collect_metrics_after", lambda: {"cpu_percent": 1})

    # monkeypatch write functions to avoid filesystem writes
    monkeypatch.setattr(ss, "_write_post_treatment_artifacts", lambda snap: None)

    # Activate by forcing critical state
    ss._activate_treatment({"cpu_percent": 99})

    # Ensure post_treatment_history updated
    # worker runs synchronously in _activate_treatment, so history should be present
    assert isinstance(ss.post_treatment_history, list)
    assert len(ss.post_treatment_history) >= 1


def test_safe_collect_handles_errors(monkeypatch):
    """Testa _safe_collect para tratamento de erros em SystemState."""
    ss = s.SystemState({}, critical_duration=1, post_treatment_wait_seconds=0)

    def bad_collect():
        raise RuntimeError("boom")

    assert ss._safe_collect(bad_collect) == {}
