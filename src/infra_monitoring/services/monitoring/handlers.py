"""Orchestration of automated treatments for critical metrics.

Selects and executes recovery actions using cooldowns and sustained-window
logic. The module coordinates treatment execution while preserving the
state and cooldown semantics used by higher-level orchestration.
"""

import time
import logging
from typing import Any

from infra_monitoring.infra.system import treatments
from infra_monitoring.infra.system.network_learning import NetworkUsageLearningHandler
from infra_monitoring.infra.config import settings

network_learning_handler = NetworkUsageLearningHandler()


logger = logging.getLogger(__name__)


# Helper: attempt_treatment — select action by normalized metric name
def _select_action(metric_lower: str) -> tuple[str | None, tuple]:
    """Select the appropriate action for a normalized metric.

    Returns a tuple (action_name, args) or (None, ()) when no action applies.
    """
    # we return only the action name and arguments; the function is
    # resolved dynamically via getattr(treatments, action_name) when
    # the treatment is executed
    if "disk" in metric_lower or "disk_percent" in metric_lower:
        return "check_disk_usage", ()
    if "memory" in metric_lower or "ram" in metric_lower or "memory_percent" in metric_lower:
        import os

        if os.name == "posix":
            return "trim_process_working_set_posix", ()
        else:
            return "trim_process_working_set_windows", ()
    if "network" in metric_lower or "ping" in metric_lower or "loss" in metric_lower or "latency" in metric_lower:
        return "reapply_network_config", ()
    if "cpu" in metric_lower:
        return "reap_zombie_processes", ()
    return None, ()


# Helper: attempt_treatment — check if action remains in cooldown
def _on_cooldown(state: Any, action_name: str, now: float) -> bool:
    """Return True if the action is still in cooldown.

    `state` is expected to provide `treatment_cooldowns` and
    `last_treatment_run` mappings.
    """
    cooldown = getattr(state, "treatment_cooldowns", {}).get(action_name, 0)
    last = getattr(state, "last_treatment_run", {}).get(action_name, 0)
    return now - last < cooldown


def _run_main_action(state: Any, action_name: str, action_func, action_args):
    """Execute the main treatment action and return its result.

    The special-case for `cleanup_temp_files` is preserved.
    """
    if action_name == "cleanup_temp_files":
        days = getattr(state, "cleanup_temp_age_days", None)
        if isinstance(days, int):
            return action_func(days)
        return action_func()

    # call with arguments only when action_args is truthy
    return action_func(*action_args) if action_args else action_func()


def _maybe_run_aux_cleanup(state: Any, now: float) -> None:
    """Attempt to run `cleanup_temp_files` as an auxiliary action (best-effort).

    Updates `state.last_treatment_run` with the timestamp when executed
    successfully.
    """
    aux_name = "cleanup_temp_files"
    try:
        if not _on_cooldown(state, aux_name, now):
            aux_func = getattr(treatments, aux_name, None)
            if aux_func is not None:
                try:
                    days = getattr(state, "cleanup_temp_age_days", None)
                    aux_res = aux_func(days) if isinstance(days, int) else aux_func()
                    if hasattr(state, "last_treatment_run") and isinstance(state.last_treatment_run, dict):
                        state.last_treatment_run[aux_name] = now
                    logger.info("treatment_attempt: auxiliary %s result=%s", aux_name, aux_res)
                except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
                    logger.debug("treatment_attempt: auxiliary %s failed: %s", aux_name, exc, exc_info=True)
        else:
            logger.debug("treatment_attempt: auxiliary %s on cooldown, skipping", aux_name)
    except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
        logger.debug("treatment_attempt: error checking/executing auxiliary %s: %s", aux_name, exc, exc_info=True)


def _run_reap_aux(state: Any, action_name: str, result, now: float) -> object | None:
    """Execute (or mark) the auxiliary action `reap_zombie_processes`.

    Return the auxiliary result (`reap_result`) preserving original behavior
    in case of exceptions.
    """
    try:
        if action_name != "reap_zombie_processes":
            try:
                reap_result = treatments.reap_zombie_processes()
            except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
                logger.debug("treatment_attempt: reap_zombie_processes failed: %s", exc, exc_info=True)
                reap_result = None
            if hasattr(state, "last_treatment_run") and isinstance(state.last_treatment_run, dict):
                state.last_treatment_run["reap_zombie_processes"] = now
        else:
            reap_result = result
    except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
        logger.debug("treatment_attempt: error executing reap_zombie_processes aux: %s", exc, exc_info=True)
        reap_result = None
    return reap_result


def attempt_treatment(state: Any, name: str, _details: dict) -> dict | bool:
    """Execute the automatic treatment for a critical metric.

    - Check that the metric has satisfied the sustained window before acting.
    - Respect cooldowns configured in `state`.
    - Return a dict with {'action': <name>, 'result': <...>} on success or False.
    """
    # Explicit filter to ignore absolute (non-treatable) metrics
    ignore_metrics = [
        "memory_used_bytes",
        "memory_total_bytes",
        "disk_used_bytes",
        "disk_total_bytes",
        "temperature_celsius",
        "latency_ms",
        "bytes_sent",
        "bytes_recv",
    ]
    if name in ignore_metrics:
        return False

    now = time.monotonic()

    since = state.critic_since.get(name)
    if since is None:
        return False
    if now - since < float(getattr(state, "sustained_critic_seconds", 300)):
        return False

    metric_lower = name.lower()
    action_name, action_args = _select_action(metric_lower)
    action_func = getattr(treatments, action_name, None) if action_name else None

    if action_name is None:
        return False

    # If this is a network treatment, trigger learning before applying the treatment
    if action_name == "reapply_network_config":
        bytes_sent = getattr(state, "bytes_sent", None)
        bytes_recv = getattr(state, "bytes_recv", None)
        if bytes_sent is not None and bytes_recv is not None:
            try:
                # Ensure arguments are integers
                bs = int(float(bytes_sent))
                br = int(float(bytes_recv))
                network_learning_handler.record_daily_usage(bs, br)
                # Update dynamic thresholds
                limit = network_learning_handler.get_current_limit()
                thresholds = settings.get_valid_thresholds()
                thresholds["bytes_sent"]["critical"] = limit
                thresholds["bytes_recv"]["critical"] = limit
            except Exception as exc:
                logger.debug("network_learning_handler.record_daily_usage failed: %s", exc, exc_info=True)

    if _on_cooldown(state, action_name, now):
        return False

    try:
        if action_func is None:
            return False
        result = _run_main_action(state, action_name, action_func, action_args)
        if action_name == "check_disk_usage":
            _maybe_run_aux_cleanup(state, now)
        _run_reap_aux(state, action_name, result, now)
        if hasattr(state, "last_treatment_run") and isinstance(state.last_treatment_run, dict):
            state.last_treatment_run[action_name] = now
        return {"action": action_name, "result": result}
    except (OSError, RuntimeError, ValueError, TypeError, AttributeError):
        return False
