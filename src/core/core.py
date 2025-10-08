"""Core do programa de monitorização.

Loop principal, emissão de snapshots e execução de rotinas de manutenção
(rotação, compressão e limpeza).
"""

import logging

from system.logs import write_log, rotate_logs, compress_old_logs, safe_remove, get_log_paths
from system.logs import ensure_log_dirs_exist
from monitoring.state import SystemState
from monitoring.averages import aggregate_last_seconds, write_average_log, ensure_last_ts_exists

# ========================
# 0. Funções auxiliares para intervalos e manutenção
# ========================


# Auxilia _run_loop; criado para centralizar leitura dos intervalos de manutenção
def _read_maintenance_intervals() -> tuple[int, int, int, int]:
    """Lê intervalos de manutenção a partir do ambiente com defaults."""
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


# Auxilia _run_loop; criado para executar rotinas de manutenção periódica
def _run_maintenance(  # noqa: C901  # TODO(maintainer): função complexa; refatorar extraindo helpers para reduzir McCabe
    now: float,
    last_rotate: float,
    last_compress: float,
    last_safe_remove: float,
    last_hourly: float,
    intervals: tuple[int, int, int, int],
) -> tuple[float, float, float, float]:
    """Executa tarefas de manutenção se os intervalos estiverem ultrapassados.

    Retorna os timestamps atualizados (last_rotate, last_compress, last_safe_remove, last_hourly).
    """
    rotate_interval, compress_interval, safe_remove_interval, hourly_interval = intervals
    # rotação periódica de logs
    if now - last_rotate >= rotate_interval:
        try:
            rotate_logs()
        except (OSError, PermissionError) as exc:
            logging.getLogger(__name__).warning("Falha ao rotacionar logs: %s", exc)
        except Exception as exc:
            # fallback: proteger o loop principal de uma falha inesperada na rotação
            logging.getLogger(__name__).debug("rotate_logs: erro inesperado: %s", exc, exc_info=True)
        last_rotate = now
    # compressão de logs antigos
    if now - last_compress >= compress_interval:
        try:
            compress_old_logs()
        except (OSError, PermissionError) as exc:
            logging.getLogger(__name__).warning("Falha ao comprimir logs: %s", exc)
        except Exception as exc:
            # fallback: proteger o loop principal de uma falha inesperada na compressão
            logging.getLogger(__name__).debug("compress_old_logs: erro inesperado: %s", exc, exc_info=True)
        last_compress = now
    # remoção segura de ficheiros temporários
    if now - last_safe_remove >= safe_remove_interval:
        try:
            safe_remove()
        except (OSError, PermissionError) as exc:
            logging.getLogger(__name__).warning("Falha ao remover ficheiros antigos: %s", exc)
        except Exception as exc:
            # fallback: proteger o loop principal de uma falha inesperada na limpeza
            logging.getLogger(__name__).debug("safe_remove: erro inesperado: %s", exc, exc_info=True)
        last_safe_remove = now
    # agregação horária (agendamento simples)
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
            last_hourly = now
    except Exception as exc:
        # Fallback genérico ao agendar hourly; registrar detalhe para depuração
        logging.getLogger(__name__).debug("Erro ao agendar agregação horária: %s", exc, exc_info=True)

    return last_rotate, last_compress, last_safe_remove, last_hourly


# ========================
# 1. Funções auxiliares para formatação e emissão de snapshots
# ========================


# Auxilia _emit_snapshot; criado para formatar mensagem humana do snapshot
def _format_human_msg(snapshot: dict | None, result: dict) -> str:
    """Formatar mensagem humana a partir do snapshot/result."""
    if isinstance(snapshot, dict):
        long_lines = snapshot.get("summary_long") or []
        if isinstance(long_lines, list) and long_lines:
            return "\n".join(str(x) for x in long_lines)
        return snapshot.get("summary_short") or f"state={result.get('state')}"
    return f"state={result.get('state')}"


# Auxilia _emit_snapshot; criado para imprimir resumo curto do snapshot
def _print_snapshot_short(snap: dict | None) -> None:
    summary_short = snap.get("summary_short") if isinstance(snap, dict) else None
    print(summary_short or "Sem dados")


# Auxilia _emit_snapshot; criado para imprimir resumo longo do snapshot
def _print_snapshot_long(snap: dict | None) -> None:
    summary_long = snap.get("summary_long") if isinstance(snap, dict) else None
    if summary_long and isinstance(summary_long, list):
        for line in summary_long:
            print(line)
    else:
        print("SNAPSHOT:", snap)


# Auxilia _run_loop; criado para emitir snapshot formatado para logs e saída
def _emit_snapshot(snapshot: dict | None, result: dict, verbose_level: int) -> None:
    """Emitir snapshot formatado para logs e, opcionalmente, para a saída.

    Se `verbose_level` for > 0, imprime uma versão humana do snapshot.
    """
    import logging

    try:
        human_msg = _format_human_msg(snapshot, result)
        try:
            write_log("monitoring", "INFO", human_msg, extra=snapshot, human_enable=False)
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
    """Loop principal de coleta e execução de tarefas de manutenção.

    Executa coletas periódicas e aciona rotinas como rotação/compressão.
    """
    state = SystemState()
    executed = 0
    import time

    intervals = _read_maintenance_intervals()

    last_rotate = 0.0
    last_compress = 0.0
    last_safe_remove = 0.0
    last_hourly = 0.0
    try:
        while True:
            # lightweight check to ensure log directories still exist; will
            # call get_log_paths() to recreate them only if missing.
            try:
                ensure_log_dirs_exist()
            except Exception as exc:
                # do not fail the loop if the lightweight check has issues
                logging.getLogger(__name__).debug("ensure_log_dirs_exist failed: %s", exc, exc_info=True)
            # Também garantir o arquivo de controle last_ts em runtime (leve)
            try:
                ensure_last_ts_exists()
            except Exception as exc:
                # não falhar o loop por problemas na verificação de last_ts
                logging.getLogger(__name__).debug("ensure_last_ts_exists failed: %s", exc, exc_info=True)
            result = state.evaluate_metrics()
            snapshot = getattr(state, "last_snapshot", None) or result.get("snapshot") or result

            _emit_snapshot(snapshot if isinstance(snapshot, dict) else None, result, verbose_level)

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
                    import time

                    time.sleep(interval)
                except Exception as exc:
                    # normalmente InterruptedError/KeyboardInterrupt — registrar em PT
                    logging.getLogger(__name__).debug("Pausa interrompida: %s", exc, exc_info=True)
    except KeyboardInterrupt:
        logging.info("Recebido KeyboardInterrupt, saindo...")
