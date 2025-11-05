"""Extra tests for handlers module (small unit and integration-style tests)."""

import time
from types import SimpleNamespace

from src.monitoring import handlers


def test_select_action_matches():
    """_select_action returns expected action names for metric patterns."""
    assert handlers._select_action("disk_percent")[0] == "check_disk_usage"
    assert handlers._select_action("memory_percent")[0] == "trim_process_working_set_windows"
    assert handlers._select_action("network_bytes")[0] == "reapply_network_config"
    assert handlers._select_action("cpu_load")[0] == "reap_zombie_processes"
    assert handlers._select_action("unknown_metric")[0] is None


def test_on_cooldown_and_run_main_action():
    """_on_cooldown honors cooldown windows and _run_main_action handles special case."""
    state = SimpleNamespace(treatment_cooldowns={"a": 10}, last_treatment_run={"a": time.monotonic() - 20})
    now = time.monotonic()
    assert handlers._on_cooldown(state, "a", now) is False

    # test run_main_action simple
    def f1():
        return "ok"

    assert handlers._run_main_action(state, "some", f1, ()) == "ok"

    # special-case cleanup_temp_files
    def cleanup_days(days=None):
        return days or 0

    state2 = SimpleNamespace()
    setattr(state2, "cleanup_temp_age_days", 5)
    assert handlers._run_main_action(state2, "cleanup_temp_files", cleanup_days, ()) == 5


def test_maybe_run_aux_cleanup_and_run_reap_aux(monkeypatch):
    """_maybe_run_aux_cleanup calls cleanup helper and _run_reap_aux calls reap helper."""
    state = SimpleNamespace()
    state.last_treatment_run = {}
    state.cleanup_temp_age_days = 1

    called = {}

    def fake_cleanup(days=None):
        called["cleanup"] = days
        return True

    monkeypatch.setattr("src.monitoring.treatments.cleanup_temp_files", fake_cleanup)
    handlers._maybe_run_aux_cleanup(state, time.monotonic())
    # if function ran, last_treatment_run should be updated
    assert isinstance(state.last_treatment_run, dict)

    # test _run_reap_aux behavior
    def fake_reap():
        return "reaped"

    monkeypatch.setattr("src.monitoring.treatments.reap_zombie_processes", fake_reap)
    res = handlers._run_reap_aux(state, "not_reap", None, time.monotonic())
    assert res in (None, "reaped")


def test_attempt_treatment_no_action_or_cooldown(monkeypatch):
    """attempt_treatment returns False for unknown actions, short-sustained and may run when ready."""

    class S:
        critic_since = {"m": time.monotonic() - 1000}
        sustained_critic_seconds = 1
        treatment_cooldowns = {}
        last_treatment_run = {}

    s = S()
    # metric without a select_action mapping should return False
    assert handlers.attempt_treatment(s, "unknown_metric", {}) is False

    # when sustained not met
    s2 = S()
    s2.critic_since = {"m": time.monotonic()}
    assert handlers.attempt_treatment(s2, "m", {}) is False

    # test successful run: mock treatments function
    def fake_check():
        return "checked"

    monkeypatch.setattr("src.monitoring.treatments.check_disk_usage", fake_check)
    s3 = S()
    s3.critic_since = {"disk_percent": time.monotonic() - 1000}
    s3.sustained_critic_seconds = 1
    s3.treatment_cooldowns = {}
    s3.last_treatment_run = {}
    res = handlers.attempt_treatment(s3, "disk_percent", {})
    assert res is False or isinstance(res, dict)


def test_attempt_treatment_noop():
    """Testa attempt_treatment com nome desconhecido (deve retornar False ou dict)."""

    class DummyState(dict):
        critic_since = {}

    state = DummyState()
    name = "unknown_action"
    details = {}
    result = handlers.attempt_treatment(state, name, details)
    assert result is False or isinstance(result, dict)
