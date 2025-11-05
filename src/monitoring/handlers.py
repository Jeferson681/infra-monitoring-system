"""Orquestrações de tratamentos automáticos para métricas críticas.

Seleção de ação e execução controlada (cooldowns, janelas de sustentação)
para correções automáticas. Comentários e logs em português.
"""

import time
import logging
from typing import Any

from . import treatments


logger = logging.getLogger(__name__)


# ========================
# 0. Seleção de ação
# ========================


# Auxilia: attempt_treatment — seleciona ação por nome da métrica
def _select_action(metric_lower: str) -> tuple[str | None, tuple]:
    """Selecione a ação apropriada para uma métrica normalizada.

    Retorna uma tupla (action_name, args) ou (None, ()) quando não houver ação.
    """
    # retornamos apenas o nome da ação e os argumentos; a função é
    # resolvida dinamicamente por getattr(treatments, action_name) quando
    # o tratamento é executado
    if "disk" in metric_lower or "disk_percent" in metric_lower:
        return "check_disk_usage", ()
    if "memory" in metric_lower or "ram" in metric_lower or "memory_percent" in metric_lower:
        return "trim_process_working_set_windows", ()
    if "network" in metric_lower or "ping" in metric_lower or "loss" in metric_lower or "latency" in metric_lower:
        return "reapply_network_config", ()
    if "cpu" in metric_lower:
        return "reap_zombie_processes", ()
    return None, ()


# ========================
# 1. Utilitários de execução
# ========================


# Auxilia: attempt_treatment — verifica se a ação está em cooldown
def _on_cooldown(state: Any, action_name: str, now: float) -> bool:
    """Retorne True se a ação ainda estiver em cooldown.

    `state` é esperado fornecer dicts `treatment_cooldowns` e `last_treatment_run`.
    """
    cooldown = getattr(state, "treatment_cooldowns", {}).get(action_name, 0)
    last = getattr(state, "last_treatment_run", {}).get(action_name, 0)
    return now - last < cooldown


def _run_main_action(state: Any, action_name: str, action_func, action_args):
    """Execute a ação principal (tratamento) e retorne o resultado.

    Mantém o caso especial para `cleanup_temp_files` sem alterar a lógica.
    """
    if action_name == "cleanup_temp_files":
        days = getattr(state, "cleanup_temp_age_days", None)
        if isinstance(days, int):
            return action_func(days)
        return action_func()

    # chamar com argumentos somente se action_args for truthy
    return action_func(*action_args) if action_args else action_func()


def _maybe_run_aux_cleanup(state: Any, now: float) -> None:
    """Tente executar `cleanup_temp_files` como ação auxiliar (melhor esforço).

    Atualize `state.last_treatment_run` com o timestamp quando executado com sucesso.
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
                    logger.info("tentativa_tratamento: auxiliar %s resultado=%s", aux_name, aux_res)
                except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
                    logger.debug("tentativa_tratamento: auxiliar %s falhou: %s", aux_name, exc, exc_info=True)
        else:
            logger.debug("tentativa_tratamento: auxiliar %s em cooldown, pulando", aux_name)
    except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
        logger.debug("tentativa_tratamento: erro verificando/realizando auxiliar %s: %s", aux_name, exc, exc_info=True)


def _run_reap_aux(state: Any, action_name: str, result, now: float) -> object | None:
    """Execute (ou marque) a ação auxiliar `reap_zombie_processes`.

    Retorne o resultado do auxiliar (`reap_result`) preservando o comportamento
    original em caso de exceção.
    """
    try:
        if action_name != "reap_zombie_processes":
            try:
                reap_result = treatments.reap_zombie_processes()
            except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
                logger.debug("tentativa_tratamento: reap_zombie_processes falhou: %s", exc, exc_info=True)
                reap_result = None
            if hasattr(state, "last_treatment_run") and isinstance(state.last_treatment_run, dict):
                state.last_treatment_run["reap_zombie_processes"] = now
        else:
            reap_result = result
    except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
        logger.debug("tentativa_tratamento: erro ao executar aux reap_zombie_processes: %s", exc, exc_info=True)
        reap_result = None
    return reap_result


# ========================
# 2. Execução de tratamentos
# ========================


def attempt_treatment(state: Any, name: str, _details: dict) -> dict | bool:
    """Execute o tratamento automático para uma métrica crítica.

    - Verifica se a métrica cumpriu o período de sustento antes de agir.
    - Respeita cooldowns configurados no `state`.
    - Retorna um dict com {'action': <name>, 'result': <...>} em sucesso ou False.
    """
    now = time.monotonic()

    since = state.critic_since.get(name)
    if since is None:
        logger.debug("tentativa_tratamento: %s ainda não sustentado", name)
        return False
    if now - since < float(getattr(state, "sustained_critic_seconds", 300)):
        elapsed = int(now - since)
        req = int(getattr(state, "sustained_critic_seconds", 300))
        logger.debug(
            "tentativa_tratamento: %s sustentado por %ds < requerido %ds",
            name,
            elapsed,
            req,
        )
        return False

    metric_lower = name.lower()
    action_name, action_args = _select_action(metric_lower)
    action_func = getattr(treatments, action_name, None) if action_name else None
    if action_name is None:
        logger.debug("tentativa_tratamento: nenhuma ação específica para métrica %s", name)
        return False

    if _on_cooldown(state, action_name, now):
        cd = getattr(state, "treatment_cooldowns", {}).get(action_name, 0)
        last_ts = getattr(state, "last_treatment_run", {}).get(action_name, 0)
        remaining = max(0, int(cd - (now - last_ts)))
        logger.debug(
            "tentativa_tratamento: pulando %s devido a cooldown (%ds restantes)",
            action_name,
            remaining,
        )
        return False

    try:
        logger.info("tentativa_tratamento: executando %s para métrica %s", action_name, name)
        if action_func is None:
            logger.debug("tentativa_tratamento: função %s não encontrada em treatments", action_name)
            return False

        # Executa a ação principal (inclui caso especial cleanup_temp_files)
        result = _run_main_action(state, action_name, action_func, action_args)

        # Se executamos um check de disco, também tentar cleanup de temporários
        # como ação auxiliar (melhor esforço), respeitando cooldown separado.
        if action_name == "check_disk_usage":
            _maybe_run_aux_cleanup(state, now)

        # Sempre tentar uma ação auxiliar de limpeza de processos zumbi quando
        # executamos um tratamento principal diferente de 'reap_zombie_processes'.
        reap_result = _run_reap_aux(state, action_name, result, now)

        # marcar último run para a ação principal
        if hasattr(state, "last_treatment_run") and isinstance(state.last_treatment_run, dict):
            state.last_treatment_run[action_name] = now
        logger.debug("tentativa_tratamento: %s retornou %s (reap=%s)", action_name, result, reap_result)
        return {"action": action_name, "result": result}
    except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
        logger.warning("tentativa_tratamento: %s falhou para %s: %s", action_name, name, exc, exc_info=True)
        return False
