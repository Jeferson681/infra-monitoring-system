import infra_monitoring.core.core as core


def test_snapshot_contains_run_id_and_cycle(monkeypatch):
    """Ensure emitted snapshots include `run_id` and `cycle` keys."""
    captured = {}

    def fake_emit(snapshot, result, verbose_level):
        captured["snapshot"] = snapshot
        captured["result"] = result

    # Patch the internal emit to capture the snapshot passed by core
    monkeypatch.setattr(core, "_emit_snapshot", fake_emit)

    # Create a minimal SystemState instance and call the collector/emitter
    state = core.SystemState({})
    core._collect_and_emit(state, verbose_level=0)

    assert "snapshot" in captured
    snap = captured["snapshot"]
    assert isinstance(snap, dict)
    # run_id should be present and non-empty
    assert "run_id" in snap and isinstance(snap["run_id"], str) and snap["run_id"]
    # cycle should be present and a positive integer
    assert "cycle" in snap and isinstance(snap["cycle"], int) and snap["cycle"] > 0
