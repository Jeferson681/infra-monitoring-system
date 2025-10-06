"""Módulo de cálculo de médias a partir de logs JSONL.

Organiza métodos principais seguidos de seus auxiliares imediatos para
facilitar leitura e manutenção (diretriz do projeto).
"""

from typing import Any, Dict, List, Iterator
import statistics
from system.logs import write_log, get_log_paths
from pathlib import Path
import json
import time
import logging

logger = logging.getLogger(__name__)

# ========================
# 0. Constantes globais para cache e estado
# ========================

STATE_CACHE_DIR_NAME = ".cache"
STATE_FILE_NAME = ".hourly_state.json"

# ========================
# 1. Funções principais de cálculo de médias
# ========================


# Função principal do módulo; calcula estatísticas horárias e registra logs
def compute_hourly_average(values: List[float]) -> Dict[str, Any]:
    """Calcular estatísticas hora e gravar logs JSON/humanos.

    Retorna um dicionário com count, mean, median, min, max, stddev.
    """
    if not values:
        stats: Dict[str, Any] = {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "stddev": None,
        }
        try:
            write_log(
                "monitoring",
                "INFO",
                "hourly average",
                extra={"hourly_average": stats},
                human_enable=False,
                json_enable=True,
            )
        except Exception as exc:
            logger.debug("failed to write json hourly log: %s", exc, exc_info=True)

        try:
            write_log(
                "monitoring-hourly",
                "INFO",
                "\n".join(["HOURLY AVERAGE:", "count: 0", "mean: N/A"]),
                extra=stats,
                human_enable=True,
                json_enable=False,
            )
        except Exception as exc:
            logger.debug("failed to write human hourly log: %s", exc, exc_info=True)

        return stats

    nums = [float(x) for x in values]
    cnt = len(nums)
    mean = statistics.mean(nums)
    med = statistics.median(nums)
    minimum = min(nums)
    maximum = max(nums)
    stddev = statistics.pstdev(nums)
    stats = {"count": cnt, "mean": mean, "median": med, "min": minimum, "max": maximum, "stddev": stddev}
    try:
        write_log(
            "monitoring",
            "INFO",
            "hourly average",
            extra={"hourly_average": stats},
            human_enable=False,
            json_enable=True,
        )
    except Exception as exc:
        logger.debug("failed to write json hourly log: %s", exc, exc_info=True)
    try:
        # também grava uma representação humana para revisão humana/console
        write_log(
            "monitoring-hourly",
            "INFO",
            "\n".join(["HOURLY AVERAGE:", f"count: {stats['count']}", f"mean: {stats['mean']}"]),
            extra=stats,
            human_enable=True,
            json_enable=False,
        )
    except Exception as exc:
        logger.debug("failed to write human hourly log (values): %s", exc, exc_info=True)
    return stats


# Auxilia _samples_from_file; criado para extrair timestamp de objetos JSONL
def _extract_timestamp(obj: dict) -> float | None:
    """Extrai um timestamp de um objeto JSONL."""
    if not isinstance(obj, dict):
        return None
    for k in ("timestamp", "time", "ts"):
        v = obj.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    for container in ("metrics_raw", "snapshot", "extra"):
        c = obj.get(container) if isinstance(obj, dict) else None
        if isinstance(c, dict):
            v = c.get("timestamp") or c.get("time") or c.get("ts")
            if isinstance(v, (int, float)):
                return float(v)
    return None


# Função principal do módulo; calcula média móvel simples
def compute_moving_average(values: List[float], window: int) -> List[float]:
    """Calcular média móvel simples sobre uma janela fixa.

    Retorna a lista de médias móveis; retorna lista vazia se insuficiente.
    """
    if window <= 0:
        raise ValueError("window must be > 0")
    n = len(values)
    if n < window:
        return []
    nums = [float(x) for x in values]
    window_sum = sum(nums[:window])
    out: List[float] = [window_sum / window]
    for i in range(window, n):
        window_sum += nums[i] - nums[i - window]
        out.append(window_sum / window)
    return out


# Função principal do módulo; executa agregação horária e persiste estado
def run_hourly_aggregation(
    metric_keys: List[str] | None = None, window_seconds: int = 3600, end_ts: float | None = None
) -> Dict[str, Any] | None:
    """Executa agregação horária para chaves de métrica e persiste estado.

    Determina intervalo alvo, coleta amostras e grava último timestamp processado.
    """
    if metric_keys is None:
        metric_keys = ["cpu_percent", "memory_percent", "disk_percent", "ping_ms"]
    state = _read_hourly_state()
    last_end = int(state.get("last_end_ts", 0))
    try:
        min_ts, max_ts = _find_min_max_ts()
    except Exception as exc:
        logger.debug("failed to determine min/max timestamps: %s", exc, exc_info=True)
        min_ts, max_ts = 0.0, 0.0
    if end_ts is not None:
        target_end = float(end_ts)
    else:
        if last_end <= 0:
            if min_ts == float("inf") or max_ts <= 0.0 or (max_ts - min_ts) < float(window_seconds):
                return None
            target_end = max_ts
        else:
            target_end = float(last_end + int(window_seconds))
    if last_end >= int(target_end):
        return None
    if max_ts > 0.0 and max_ts < target_end:
        return None
    start_ts = float(target_end - float(window_seconds))
    samples = _collect_samples(start_ts, target_end, metric_keys)
    stats = compute_hourly_average(samples)
    try:
        state["last_end_ts"] = int(target_end)
        _write_hourly_state(state)
    except Exception as exc:
        logger.debug("failed to update hourly state: %s", exc, exc_info=True)
    return stats


# ========================
# 2. Funções auxiliares para leitura, escrita e coleta de amostras
# ========================


# Auxilia run_hourly_aggregation; criado para ler estado salvo do disco
def _read_hourly_state() -> dict:
    """Lê o estado salvo (se existir) e devolve um dicionário."""
    _migrate_old_state()
    root = get_log_paths().root
    cache_dir = Path(root) / STATE_CACHE_DIR_NAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    p = cache_dir / STATE_FILE_NAME
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        logger.debug("failed reading hourly state %s: %s", p, exc, exc_info=True)
        return {}


# Auxilia run_hourly_aggregation; criado para migrar arquivo de estado antigo
def _migrate_old_state() -> None:
    """Migrar formato/posição antiga do arquivo de estado."""
    try:
        lp = get_log_paths()
        root = lp.root
        old = Path(root) / STATE_FILE_NAME
        cache_dir = Path(root) / STATE_CACHE_DIR_NAME
        cache_dir.mkdir(parents=True, exist_ok=True)
        new = cache_dir / STATE_FILE_NAME
        if old.exists() and not new.exists():
            new.parent.mkdir(parents=True, exist_ok=True)
            old.replace(new)
    except Exception as exc:
        logger.debug("failed to migrate old hourly state: %s", exc, exc_info=True)
        return


# Auxilia run_hourly_aggregation; criado para gravar estado atualizado no disco
def _write_hourly_state(d: dict) -> None:
    """Grava o dicionário de estado no arquivo de cache."""
    root = get_log_paths().root
    cache_dir = Path(root) / STATE_CACHE_DIR_NAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    p = cache_dir / STATE_FILE_NAME
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
    except Exception as exc:
        logger.debug("failed to write hourly state file %s: %s", p, exc, exc_info=True)


# Auxilia run_hourly_aggregation; criado para coletar amostras entre dois timestamps
def _collect_samples(start_ts: float, end_ts: float, metric_keys: List[str]) -> List[float]:
    """Coleta amostras entre dois timestamps a partir de arquivos JSONL."""
    json_dir = get_log_paths().json_dir
    samples: List[float] = []
    start_date = time.gmtime(start_ts)
    end_date = time.gmtime(end_ts)
    dates = {time.strftime("%Y-%m-%d", start_date), time.strftime("%Y-%m-%d", end_date)}
    for d in sorted(dates):
        fname = json_dir / f"monitoring-{d}.jsonl"
        if not fname.exists():
            continue
        samples.extend(_samples_from_file(fname, start_ts, end_ts, metric_keys))
    return samples


# Auxilia _collect_samples; criado para ler arquivo JSONL e extrair amostras válidas
def _samples_from_file(fname: Path, start_ts: float, end_ts: float, metric_keys: List[str]) -> List[float]:
    """Lê um arquivo JSONL e retorna amostras válidas no intervalo.

    Usa `_extract_timestamp` e `_extract_metric_value` (helpers locais).
    """
    out: List[float] = []
    for obj in _iter_jsonl_objects(fname):
        ts = _extract_timestamp(obj)
        if ts is None or not (start_ts <= ts <= end_ts):
            continue
        v = _extract_metric_value(obj, metric_keys)
        if v is not None:
            out.append(v)
    return out


# Auxilia _samples_from_file e _find_min_max_ts; criado para iterar objetos JSON válidos
def _iter_jsonl_objects(fname: Path) -> Iterator[dict]:
    """Iterador simples sobre objetos JSON válidos em um arquivo JSONL.

    Centraliza a lógica de abertura/decodificação do arquivo para evitar
    duplicação entre helpers que precisam ler JSONL.
    """
    try:
        with open(fname, "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield obj
    except Exception as exc:
        logger.debug("failed reading jsonl %s: %s", fname, exc, exc_info=True)
        return


# Auxilia _samples_from_file; criado para extrair valor de métrica das chaves fornecidas
def _extract_metric_value(obj: dict, metric_keys: List[str]) -> float | None:
    """Extrai o primeiro valor válido encontrado nas chaves fornecidas."""
    if not isinstance(obj, dict):
        return None
    for k in metric_keys:
        v = obj.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    for container in ("metrics_raw", "snapshot", "extra"):
        c = obj.get(container) if isinstance(obj, dict) else None
        if not isinstance(c, dict):
            continue
        for k in metric_keys:
            v = c.get(k)
            if isinstance(v, (int, float)):
                return float(v)
    return None


# Auxilia run_hourly_aggregation; criado para reduzir complexidade de run_hourly_aggregation
def _find_min_max_ts() -> (
    tuple[float, float]
):  # noqa: C901 — complexidade inflada por try/except; mantido assim para evitar helpers artificiais
    """Procura o menor e maior timestamp disponível nos arquivos JSONL."""
    json_dir = get_log_paths().json_dir
    min_ts = float("inf")
    max_ts = 0.0
    found = False
    for p in sorted(json_dir.glob("monitoring-*.jsonl")):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = _extract_timestamp(obj)
                    if isinstance(ts, (int, float)):
                        found = True
                        if ts < min_ts:
                            min_ts = float(ts)
                        if ts > max_ts:
                            max_ts = float(ts)
        except Exception as exc:
            logger.debug("error scanning jsonl %s: %s", p, exc, exc_info=True)
            continue
    if not found:
        return 0.0, 0.0
    return float(min_ts), float(max_ts)


def ensure_hourly_state_exists() -> None:
    """Garante que exista um estado mínimo no cache (compatibilidade API).

    Cria `last_end_ts: 0` quando não existir. Mantido para compatibilidade com callers.
    """
    try:
        _migrate_old_state()
        lp = get_log_paths()
        cache_dir = Path(lp.root) / STATE_CACHE_DIR_NAME
        cache_dir.mkdir(parents=True, exist_ok=True)
        p = cache_dir / STATE_FILE_NAME
        if not p.exists():
            _write_hourly_state({"last_end_ts": 0})
    except Exception as exc:
        logger.debug("ensure_hourly_state_exists failed: %s", exc, exc_info=True)
