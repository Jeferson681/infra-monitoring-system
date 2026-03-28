def test_import_state():
    """Importa o módulo state sem erros."""
    # module should expose compute_metric_states and SystemState
    import inspect

    import infra_monitoring.services.monitoring.state as state

    assert state is not None
    fn = getattr(state, "compute_metric_states", None)
    assert fn is not None and callable(fn)
    sig = inspect.signature(fn)
    assert len(sig.parameters) >= 1
    assert hasattr(state, "SystemState")


def test_compute_metric_states_and_systemstate_basic():
    import infra_monitoring.services.monitoring.state as state

    thresholds = {"cpu_percent": {"warning": 50.0, "critical": 90.0}}
    metrics = {"cpu_percent": 95.0}
    out = state.compute_metric_states(metrics, thresholds)
    # resulting mapping should include the mapped state for cpu
    assert isinstance(out, dict)
    # check corresponding state key exists and is CRITICAL
    assert out.get("state_cpu") == state.STATE_CRITICAL

    # SystemState evaluate_metrics should return CRITICAL for same inputs
    ss = state.SystemState(thresholds)
    res = ss.evaluate_metrics(metrics)
    assert isinstance(res, str) and res == state.STATE_CRITICAL
