"""Helpers de manutenção (rotações, compressão, remoção segura e agregação horária).

Extraído de `core` para centralizar rotinas periódicas e permitir testes isolados.
"""

from __future__ import annotations

import logging


from ..system.logs import rotate_logs, compress_old_logs, safe_remove, get_log_paths
from ..monitoring.averages import aggregate_last_seconds, write_average_log


def _read_maintenance_intervals() -> tuple[int, int, int, int]:
    """Lê intervalos de manutenção a partir do ambiente com defaults.

    Retorna (rotate_interval, compress_interval, safe_remove_interval, hourly_interval)
    em segundos. Valores inválidos nas variáveis de ambiente são tratados com
    defaults seguros.
    """
    import os

    try:
        rotate_interval = int(os.getenv("MONITORING_ROTATE_INTERVAL_SEC", str(24 * 3600)))
    except (TypeError, ValueError):
        rotate_interval = 24 * 3600
    try:
        compress_interval = int(os.getenv("MONITORING_COMPRESS_INTERVAL_SEC", str(60 * 60)))
    except (TypeError, ValueError):
        compress_interval = 60 * 60
    try:
        safe_remove_interval = int(os.getenv("MONITORING_SAFE_REMOVE_INTERVAL_SEC", str(24 * 3600 * 7)))
    except (TypeError, ValueError):
        safe_remove_interval = 24 * 3600 * 7
    try:
        hourly_interval = int(os.getenv("MONITORING_HOURLY_INTERVAL_SEC", str(3600)))
    except (TypeError, ValueError):
        hourly_interval = 3600
    return rotate_interval, compress_interval, safe_remove_interval, hourly_interval


def _maintenance_rotate(now: float, last_rotate: float, rotate_interval: int) -> float:
    """Execute rotação de logs quando o intervalo for atingido.

    Retorna o novo timestamp de `last_rotate` (usado para agendamento).
    """
    if now - last_rotate >= rotate_interval:
        try:
            rotate_logs()
        except OSError as exc:
            logging.getLogger(__name__).warning("Falha ao rotacionar logs: %s", exc)
        except Exception as exc:
            logging.getLogger(__name__).debug("rotate_logs: erro inesperado: %s", exc, exc_info=True)
        return now
    return last_rotate


def _maintenance_compress(now: float, last_compress: float, compress_interval: int) -> float:
    """Execute compressão de logs quando o intervalo for atingido.

    Retorna o novo timestamp de `last_compress`.
    """
    if now - last_compress >= compress_interval:
        try:
            compress_old_logs()
        except OSError as exc:
            logging.getLogger(__name__).warning("Falha ao comprimir logs: %s", exc)
        except Exception as exc:
            logging.getLogger(__name__).debug("compress_old_logs: erro inesperado: %s", exc, exc_info=True)
        return now
    return last_compress


def _maintenance_safe_remove(now: float, last_safe_remove: float, safe_remove_interval: int) -> float:
    """Execute remoção segura (safe remove) quando o intervalo for atingido.

    Retorna o novo timestamp de `last_safe_remove`.
    """
    if now - last_safe_remove >= safe_remove_interval:
        try:
            safe_remove()
        except OSError as exc:
            logging.getLogger(__name__).warning("Falha ao remover ficheiros antigos: %s", exc)
        except Exception as exc:
            logging.getLogger(__name__).debug("safe_remove: erro inesperado: %s", exc, exc_info=True)
        return now
    return last_safe_remove


def _maintenance_hourly(now: float, last_hourly: float, hourly_interval: int) -> float:
    """Agende e execute tarefa horária de agregação de métricas.

    Tenta agregar os últimos `hourly_interval` segundos de logs e gravá-los.
    Retorna o novo timestamp de `last_hourly` em sucesso, senão retorna o valor antigo.
    """
    try:
        if now - last_hourly >= hourly_interval:
            try:
                lp = get_log_paths()
                root = lp.root
                agg = aggregate_last_seconds(logs_root=root, seconds=hourly_interval)

                if agg:
                    try:
                        write_average_log(agg, hourly=True, hourly_window_seconds=hourly_interval)
                    except Exception as exc:
                        logging.getLogger(__name__).debug("write_average_log failed: %s", exc, exc_info=True)
            except Exception as exc:
                logging.getLogger(__name__).debug("Falha na agregação horária: %s", exc, exc_info=True)
            return now
    except Exception as exc:
        logging.getLogger(__name__).debug("Erro ao agendar agregação horária: %s", exc, exc_info=True)
    return last_hourly


def _run_maintenance(
    now: float,
    last_rotate: float,
    last_compress: float,
    last_safe_remove: float,
    last_hourly: float,
    intervals: tuple[int, int, int, int],
) -> tuple[float, float, float, float]:
    """Executa tarefas de manutenção periódicas.

    Recebe os timestamps de referência e os intervalos e retorna os timestamps
    potencialmente atualizados após executar as tarefas necessárias.
    """
    rotate_interval, compress_interval, safe_remove_interval, hourly_interval = intervals

    last_rotate = _maintenance_rotate(now, last_rotate, rotate_interval)
    last_compress = _maintenance_compress(now, last_compress, compress_interval)
    last_safe_remove = _maintenance_safe_remove(now, last_safe_remove, safe_remove_interval)
    last_hourly = _maintenance_hourly(now, last_hourly, hourly_interval)

    return last_rotate, last_compress, last_safe_remove, last_hourly
