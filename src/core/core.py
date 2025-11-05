"""Core do programa de monitorização.

Loop principal, emissão de snapshots e execução de rotinas de manutenção
(rotação, compressão e limpeza).
"""

import logging

from .emitter import emit_snapshot as _emit_snapshot

from ..system.logs import ensure_log_dirs_exist
from ..system.maintenance import _read_maintenance_intervals, _run_maintenance
from ..monitoring.state import SystemState
from ..config.settings import get_valid_thresholds
from ..monitoring.metrics import collect_metrics as _collect_metrics
from ..monitoring.averages import ensure_last_ts_exists

_NO_DATA_STR = "Sem dados"

# Maintenance helpers are provided by `src.system.maintenance` and imported above.


# ========================
# 1. Funções auxiliares para formatação e emissão de snapshots
# ========================


# Auxilia _emit_snapshot; criado para formatar mensagem humana do snapshot

# Auxilia _emit_snapshot; criado para imprimir resumo curto do snapshot

# Auxilia _emit_snapshot; criado para imprimir resumo longo do snapshot

# Auxilia _run_loop; responsável por emitir snapshot via emitter module


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
