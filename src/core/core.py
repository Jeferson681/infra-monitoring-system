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

# Helpers de manutenção estão em `src.system.maintenance` (importados acima).


# ========================
# 1. Funções auxiliares para formatação e emissão de snapshots
# ========================


# ========================
# 2. Loop principal do monitoramento
# ========================


# Função principal do módulo; executa o loop de coleta e manutenção
def run_loop(interval: float, cycles: int, verbose_level: int) -> None:
    """Loop principal do monitor que coleta métricas e executa manutenção.

    Parâmetros:
        interval: atraso entre ciclos em segundos (float).
        cycles: número de ciclos a executar (0 = infinito).
        verbose_level: controla o nível de saída humana (0 = silencioso).
    """
    import time

    thresholds = get_valid_thresholds()
    state = SystemState(thresholds)
    # Obs: o parser de argumentos (`src.core.args.parse_args`) já aplica overrides
    # via variáveis de ambiente quando adequado (prioridade: CLI > ENV > default).
    # Não re-ler env aqui para evitar que variáveis de ambiente sobrescrevam
    # valores fornecidos explicitamente pela linha de comando.
    executed = 0
    intervals = _read_maintenance_intervals()
    last_rotate = 0.0
    last_compress = 0.0
    last_safe_remove = 0.0
    last_hourly = 0.0
    try:
        while True:
            _ensure_runtime_checks()
            _collect_and_emit(state, verbose_level)
            now = time.monotonic()
            try:
                last_rotate, last_compress, last_safe_remove, last_hourly = _run_maintenance(
                    now, last_rotate, last_compress, last_safe_remove, last_hourly, intervals
                )
            except Exception as exc:
                logging.getLogger(__name__).debug("Erro ao agendar manutenção: %s", exc, exc_info=True)
            executed += 1
            if cycles != 0 and executed >= cycles:
                break
            if interval > 0.0:
                try:
                    time.sleep(interval)
                except Exception as exc:
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
        # não falhar o loop se a verificação leve apresentar problemas
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

        # Aprendizagem diária do consumo de rede: registra bytes enviados/recebidos todo ciclo
        try:
            from src.monitoring.handlers import network_learning_handler

            bytes_sent = metrics.get("bytes_sent")
            bytes_recv = metrics.get("bytes_recv")
            if bytes_sent is not None and bytes_recv is not None:
                # Garante que os argumentos sejam inteiros
                try:
                    bs = int(float(bytes_sent))
                    br = int(float(bytes_recv))
                    network_learning_handler.record_daily_usage(bs, br)
                except (ValueError, TypeError):
                    pass
        except Exception as exc:
            import logging

            logging.getLogger(__name__).debug("Falha ao registrar aprendizagem diária de rede: %s", exc, exc_info=True)

    state_name = state.evaluate_metrics(metrics)
    # Após avaliar métricas, verificar e tentar tratamento para cada métrica crítica
    from src.monitoring.handlers import attempt_treatment

    thresholds = getattr(state, "thresholds", {})
    for metric_name, limits in thresholds.items():
        crit = limits.get("critical")
        value = metrics.get(metric_name)
        if crit is not None and value is not None and value >= crit:
            # Detalhes podem ser extendidos conforme necessário
            attempt_treatment(state, metric_name, {"value": value, "threshold": crit})
    result = {"state": state_name, "metrics": metrics}
    snapshot = getattr(state, "current_snapshot", None)
    _emit_snapshot(snapshot if isinstance(snapshot, dict) else None, result, verbose_level)
    return result


# Tornar a função disponível também sem a versão pública para retrocompatibilidade
# (algumas referências internas/tests podem usar o nome com underscore).
_run_loop = run_loop
