"""Core do programa de monitorização.

Loop principal, emissão de snapshots e execução de rotinas de manutenção
(rotação, compressão e limpeza).
"""

import logging
from ..monitoring.formatters import normalize_for_display, format_snapshot_human

from ..system.logs import write_log, rotate_logs, compress_old_logs, safe_remove, get_log_paths
from ..system.logs import ensure_log_dirs_exist
from ..monitoring.state import SystemState
from ..config.settings import get_valid_thresholds
from ..monitoring.metrics import collect_metrics as _collect_metrics
from ..monitoring.averages import aggregate_last_seconds, write_average_log, ensure_last_ts_exists

_NO_DATA_STR = "Sem dados"

# ========================
# 0. Funções auxiliares para intervalos e manutenção
# ========================


# Auxilia _run_loop; criado para centralizar leitura dos intervalos de manutenção
def _read_maintenance_intervals() -> tuple[int, int, int, int]:
    """Lê intervalos de manutenção a partir do ambiente com defaults.

    Retorna uma tupla com (rotate_interval, compress_interval, safe_remove_interval, hourly_interval)
    em segundos. Valores inválidos nas variáveis de ambiente são substituídos por defaults seguros.
    """
    import os

    try:
        rotate_interval = int(os.getenv("MONITORING_ROTATE_INTERVAL_SEC", str(24 * 3600)))
    except (TypeError, ValueError):
        # fallback: variável de ambiente inválida -> usar default
        rotate_interval = 24 * 3600
    try:
        compress_interval = int(os.getenv("MONITORING_COMPRESS_INTERVAL_SEC", str(60 * 60)))
    except (TypeError, ValueError):
        # fallback: variável de ambiente inválida -> usar default
        compress_interval = 60 * 60
    try:
        safe_remove_interval = int(os.getenv("MONITORING_SAFE_REMOVE_INTERVAL_SEC", str(24 * 3600 * 7)))
    except (TypeError, ValueError):
        # fallback: variável de ambiente inválida -> usar default
        safe_remove_interval = 24 * 3600 * 7
    try:
        hourly_interval = int(os.getenv("MONITORING_HOURLY_INTERVAL_SEC", str(3600)))
    except (TypeError, ValueError):
        # fallback: variável de ambiente inválida -> usar default
        hourly_interval = 3600
    return rotate_interval, compress_interval, safe_remove_interval, hourly_interval


# Module-level maintenance helpers extracted to reduce cyclomatic complexity


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
            # fallback: proteger o loop principal de uma falha inesperada na rotação
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
            # fallback: proteger o loop principal de uma falha inesperada na compressão
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
            # fallback: proteger o loop principal de uma falha inesperada na limpeza
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
                # Resolve log root from logging subsystem and run aggregation
                lp = get_log_paths()
                root = lp.root
                agg = aggregate_last_seconds(logs_root=root, seconds=hourly_interval)

                if agg:
                    try:
                        write_average_log(agg, hourly=True, hourly_window_seconds=hourly_interval)
                    except Exception as exc:
                        logging.getLogger(__name__).debug("write_average_log failed: %s", exc, exc_info=True)
            except Exception as exc:
                # fallback: evitar que erro no hourly interrompa o loop principal
                logging.getLogger(__name__).debug("Falha na agregação horária: %s", exc, exc_info=True)
            return now
    except Exception as exc:
        # Fallback genérico ao agendar hourly; registrar detalhe para depuração
        logging.getLogger(__name__).debug("Erro ao agendar agregação horária: %s", exc, exc_info=True)
    return last_hourly


# Auxilia _run_loop; criado para executar rotinas de manutenção periódica
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


# ========================
# 1. Funções auxiliares para formatação e emissão de snapshots
# ========================


# Auxilia _emit_snapshot; criado para formatar mensagem humana do snapshot
def _format_human_msg(snapshot: dict | None, result: dict) -> str:
    """Formata uma mensagem legível a partir do snapshot/result.

    Prioriza campos 'summary_short' e 'summary_long' quando disponíveis. Caso
    contrário, delega para o formatador comum ou constrói um fallback simples.
    """
    # Delegate full human message formatting to the centralized formatter
    try:
        return format_snapshot_human(snapshot, result)
    except Exception:
        # fallback to minimal representation on error
        return f"state={result.get('state')}"


# Auxilia _emit_snapshot; criado para imprimir resumo curto do snapshot
def _print_snapshot_short(snap: dict | None) -> None:
    """Imprime um resumo curto do snapshot na saída padrão.

    Mostra 'Sem dados' quando o snapshot não estiver disponível.
    """
    if not isinstance(snap, dict):
        print(_NO_DATA_STR)
        return

    summary_short = snap.get("summary_short")
    if summary_short:
        print(summary_short)
        return

    # Build short summary from metrics using shared formatter when available
    metrics = snap.get("metrics")
    if isinstance(metrics, dict):
        nf = normalize_for_display(metrics)
        print(nf.get("summary_short") or _NO_DATA_STR)
        return

    print(_NO_DATA_STR)


# Auxilia _emit_snapshot; criado para imprimir resumo longo do snapshot
def _print_snapshot_long(snap: dict | None) -> None:
    """Imprime versão longa do snapshot na saída padrão.

    Quando não houver resumo longo tenta montar um a partir das métricas.
    """
    if not isinstance(snap, dict):
        print("SNAPSHOT: Sem dados")
        return

    summary_long = snap.get("summary_long")
    if summary_long and isinstance(summary_long, list):
        for line in summary_long:
            print(line)
        return

    # If no explicit long summary, build one from metrics using shared formatter
    metrics = snap.get("metrics")
    if isinstance(metrics, dict):
        nf = normalize_for_display(metrics)
        long_lines = nf.get("summary_long") or []
        if isinstance(long_lines, list) and long_lines:
            for line in long_lines:
                print(line)
            return

    # Fallback: preserve original SNAPSHOT: <repr>
    print("SNAPSHOT:", snap)


# Auxilia _run_loop; criado para emitir snapshot formatado para logs e saída
def _emit_snapshot(snapshot: dict | None, result: dict, verbose_level: int) -> None:
    """Emita o snapshot para os subsistemas de logging e, opcionalmente, para stdout.

    - Escreve ambos os formatos (humano e JSON) para os logs.
    - Se `verbose_level` > 0, também imprime uma versão humana (curta/longa).
    """
    import logging

    try:
        human_msg = _format_human_msg(snapshot, result)
        try:
            # write only JSON for the main monitoring feed (single-line JSONL);
            # do not write the human text to the canonical `monitoring` file here.
            write_log("monitoring", "INFO", human_msg, extra=snapshot, human_enable=False, json_enable=True)
        except Exception as exc:
            # fallback: não permitir que falha de logging quebre a emissão do snapshot
            logging.getLogger(__name__).info("Falha ao escrever log via write_log: %s", exc)
    except Exception:
        logging.getLogger(__name__).info("Falha ao construir/emitir snapshot", exc_info=True)

    if not verbose_level:
        return

    if verbose_level == 1:
        _print_snapshot_short(snapshot)
    else:
        _print_snapshot_long(snapshot)


# ========================
# 2. Loop principal do monitoramento
# ========================


# Função principal do módulo; executa o loop de coleta e manutenção
def _run_loop(interval: float, cycles: int, verbose_level: int) -> None:
    """Loop principal do monitor que coleta métricas e executa manutenção.

    Parâmetros:
        interval: atraso entre ciclos em segundos (float).
        cycles: número de ciclos a executar (0 = infinito).
        verbose_level: controla o nível de saída humana (0 = silencioso).
    """
    # build validated thresholds and create SystemState
    thresholds = get_valid_thresholds()
    state = SystemState(thresholds)
    executed = 0
    import time

    intervals = _read_maintenance_intervals()

    last_rotate = 0.0
    last_compress = 0.0
    last_safe_remove = 0.0
    last_hourly = 0.0

    try:
        while True:
            # lightweight runtime checks (log dirs, last_ts)
            _ensure_runtime_checks()

            # collect metrics, evaluate and emit snapshot
            _collect_and_emit(state, verbose_level)

            now = time.monotonic()
            try:
                # delega manutenção para helper reutilizável
                last_rotate, last_compress, last_safe_remove, last_hourly = _run_maintenance(
                    now, last_rotate, last_compress, last_safe_remove, last_hourly, intervals
                )
            except Exception as exc:
                # fallback: proteger loop principal de erros de scheduling
                logging.getLogger(__name__).debug("Erro ao agendar manutenção: %s", exc, exc_info=True)

            executed += 1
            if cycles != 0 and executed >= cycles:
                break

            if interval > 0.0:
                try:
                    time.sleep(interval)
                except Exception as exc:
                    # normalmente InterruptedError/KeyboardInterrupt — registrar em PT
                    logging.getLogger(__name__).debug("Pausa interrompida: %s", exc, exc_info=True)
    except KeyboardInterrupt:
        logging.info("Recebido KeyboardInterrupt, saindo...")


def _ensure_runtime_checks() -> None:
    """Verificações leves de runtime executadas antes de cada coleta.

    Garante que os diretórios de logs existem e que o arquivo last_ts está presente.
    Falhas são tratadas em modo 'best-effort' para não interromper o loop.
    """
    try:
        ensure_log_dirs_exist()
    except Exception as exc:
        # do not fail the loop if the lightweight check has issues
        logging.getLogger(__name__).debug("ensure_log_dirs_exist failed: %s", exc, exc_info=True)
    try:
        ensure_last_ts_exists()
    except Exception as exc:
        # não falhar o loop por problemas na verificação de last_ts
        logging.getLogger(__name__).debug("ensure_last_ts_exists failed: %s", exc, exc_info=True)


def _collect_and_emit(state: SystemState, verbose_level: int) -> dict:
    """Coleta métricas, avalia o estado e emite o snapshot.

    Retorna o dicionário de resultado: {'state': <str>, 'metrics': <dict>}.
    """
    try:
        metrics = _collect_metrics()
    except Exception:
        metrics = {}

    state_name = state.evaluate_metrics(metrics)
    result = {"state": state_name, "metrics": metrics}
    snapshot = getattr(state, "current_snapshot", None)
    _emit_snapshot(snapshot if isinstance(snapshot, dict) else None, result, verbose_level)
    return result
