"""Orquestrações de tratamentos automáticos para métricas críticas.

Seleção de ação e execução controlada (cooldowns, janelas de sustentação)
para correções automáticas. Comentários e logs em português.
"""

import time
import logging
from typing import Any

from src.system import treatments
from src.system.network_learning import NetworkUsageLearningHandler
from src.config import settings

network_learning_handler = NetworkUsageLearningHandler()


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
    # Filtro explícito para ignorar métricas absolutas (não tratáveis)
    ignore_metrics = [
        "memory_used_bytes",
        "memory_total_bytes",
        "disk_used_bytes",
        "disk_total_bytes",
        "temperature",
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

    # Se for tratamento de rede, acione o aprendizado antes do tratamento
    if action_name == "reapply_network_config":
        bytes_sent = getattr(state, "bytes_sent", None)
        bytes_recv = getattr(state, "bytes_recv", None)
        if bytes_sent is not None and bytes_recv is not None:
            try:
                # Garante que os argumentos sejam inteiros
                bs = int(float(bytes_sent))
                br = int(float(bytes_recv))
                network_learning_handler.record_daily_usage(bs, br)
                # Atualiza thresholds dinâmicos
                limit = network_learning_handler.get_current_limit()
                thresholds = settings.get_valid_thresholds()
                thresholds["bytes_sent"]["critical"] = limit
                thresholds["bytes_recv"]["critical"] = limit
            except Exception as exc:
                logger.debug("network_learning_handler.record_daily_usage falhou: %s", exc, exc_info=True)

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
