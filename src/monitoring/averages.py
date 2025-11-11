"""Cálculo e persistência de médias/estatísticas agregadas.

Este módulo contém utilitários para iterar sobre arquivos JSONL de
monitoramento, agregar janelas temporais, computar médias por métrica,
contagens por estado e gerar linhas de saída legíveis por humanos.

Principais responsabilidades:
- localizar os ficheiros JSONL do dia
- iterar objetos JSON válidos (ignorando linhas malformadas)
- agregar janelas temporais e calcular médias/contagens
- produzir saídas usadas por rotinas de manutenção e relatórios

Nota: as implementações internas tentam ser resilientes a erros de I/O
e mantêm compatibilidade com a API usada pelos testes.
"""

from pathlib import Path
from typing import Iterator, Optional, Dict, Any, List
import json
import datetime
import logging
from .formatters import _build_long_from_metrics, _fmt_bytes_human, format_used_files_lines, format_duration
from .state import compute_metric_states
from ..system.logs import write_log
from ..system.time_helpers import extract_epoch

# imports kept minimal; avoid unused imports that ruff flags

# do not import iter_jsonl_objects from averages (may be removed); decode JSONL inline


def _find_candidate_files(root: Path) -> List[Path]:
    t = datetime.date.today().strftime("%Y-%m-%d")
    return [
        root / "logs" / "json" / "monitoring" / f"monitoring-{t}.jsonl",
        root / "logs" / "json" / f"monitoring-{t}.jsonl",
        root / "json" / "monitoring" / f"monitoring-{t}.jsonl",
        root / "json" / f"monitoring-{t}.jsonl",
    ]


def _iter_jsonl_file(path: Path) -> Iterator[tuple[dict, Path, int]]:
    """Yield JSON objects from a single file path, skipping malformed lines."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            for lineno, ln in enumerate(fh, start=1):
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    obj = json.loads(ln)
                except json.JSONDecodeError:
                    # ignore malformed JSON lines
                    continue
                if isinstance(obj, dict):
                    yield obj, path, lineno
    except Exception as exc:
        logging.getLogger(__name__).error("_iter_jsonl_file: failed reading %s: %s", path, exc, exc_info=True)


def _iter_jsonl_today(logs_root: Path) -> Iterator[tuple[dict, Path, int]]:
    """Itera objetos JSON válidos do arquivo do dia em possíveis localizações.

    Abre o arquivo candidato e decodifica cada linha JSON (ignora linhas inválidas).
    """
    for c in _find_candidate_files(logs_root):
        if not c.exists():
            continue
        for obj_tuple in _iter_jsonl_file(c):
            yield obj_tuple


# --- Extracted helpers for epoch parsing (moved to module level to reduce
# complexity inside _extract_epoch)


def _human_bytes(b: Optional[float]) -> Optional[str]:
    """Compatibility wrapper: delegate to formatters._fmt_bytes_human.

    Keeps the old averages._human_bytes API used by tests and callers.
    Returns None when input is None or invalid.
    """
    if b is None:
        return None
    try:
        return _fmt_bytes_human(int(b))
    except Exception:
        return None


# _human_bytes removed: use formatters._fmt_bytes_human directly where needed.


def _compute_averages_and_counts(window: List[tuple], metric_keys: List[str]):
    """Compute sums, counts, averages and counts_by_state for a given window.

    Returns (averages, counts, counts_by_state_per_metric, state_counts).
    """
    sums: Dict[str, float] = dict.fromkeys(metric_keys, 0.0)
    counts: Dict[str, int] = dict.fromkeys(metric_keys, 0)
    counts_by_state_per_metric: Dict[str, Dict[str, int]] = {k: {} for k in metric_keys}
    state_counts: Dict[str, int] = {}

    for o, _ts, _p, _ln in window:
        _process_window_item(o, metric_keys, sums, counts, counts_by_state_per_metric, state_counts)

    averages: Dict[str, Optional[float]] = {}
    for k in metric_keys:
        cnt = counts.get(k, 0) or 0
        if cnt == 0:
            averages[k] = None
        else:
            averages[k] = sums.get(k, 0.0) / float(cnt)

    return averages, counts, counts_by_state_per_metric, state_counts


def _process_window_item(
    o: dict,
    metric_keys: List[str],
    sums: Dict[str, float],
    counts: Dict[str, int],
    counts_by_state_per_metric: Dict[str, Dict[str, int]],
    state_counts: Dict[str, int],
) -> None:
    """Process a single window item and update aggregates in-place.

    Extracted to reduce complexity of the aggregator while preserving logic.
    """
    rel = extract_relevant(o)
    st_global = _normalize_state(rel.get("state"))
    if st_global is not None:
        state_counts[st_global] = state_counts.get(st_global, 0) + 1

    # Use compute_metric_states (centralizado em state.py) para obter estados individuais
    metrics_for_state = {k: rel.get(k) for k in metric_keys}
    # manter compatibilidade; pode ser atualizado para passar thresholds reais
    thresholds = {}  # type: Dict[str, Dict[str, Any]]
    metric_states = compute_metric_states(metrics_for_state, thresholds)

    # Mapeamento de métrica para campo de estado individual (consistente com state.py)
    state_field_map = {
        "cpu_percent": "state_cpu",
        "memory_used_bytes": "state_ram",
        "disk_used_bytes": "state_disk",
        "ping_ms": "state_ping",
        "latency_ms": "state_latency",
        "bytes_sent": "state_bytes_sent",
        "bytes_recv": "state_bytes_recv",
    }

    for k in metric_keys:
        v = rel.get(k)
        if v is None:
            continue
        try:
            num = float(v)
        except (TypeError, ValueError):
            continue
        sums[k] = sums.get(k, 0.0) + num
        counts[k] = (counts.get(k, 0) or 0) + 1
        # Estado individual da métrica, se existir
        st_metric = None
        state_field = state_field_map.get(k)
        if state_field and metric_states.get(state_field):
            st_metric = _normalize_state(metric_states.get(state_field))
        else:
            st_metric = st_global
        if st_metric is not None:
            d = counts_by_state_per_metric.get(k) or {}
            d[st_metric] = d.get(st_metric, 0) + 1
            counts_by_state_per_metric[k] = d


def _compute_state_durations(sorted_window: List[tuple]) -> tuple[Dict[str, float], Dict[str, str]]:
    state_durations: Dict[str, float] = {}

    for i in range(len(sorted_window) - 1):
        o_curr, ts_curr, _, _ = sorted_window[i]
        _, ts_next, _, _ = sorted_window[i + 1]
        dur = ts_next - ts_curr
        st = _normalize_state(extract_relevant(o_curr).get("state"))
        if st is None:
            continue
        state_durations[st] = state_durations.get(st, 0.0) + float(dur)

    # Use centralized formatter for durations to keep presentation consistent
    state_durations_human: Dict[str, str] = (
        {k: format_duration(v) for k, v in state_durations.items()} if state_durations else {}
    )
    return state_durations, state_durations_human


def _compute_time_from_to(window: List[tuple]) -> tuple[str, str]:
    """Return (time_from_iso, time_to_iso) for the given window of (o, ts, p, ln).

    Small helper to keep aggregate_last_seconds simpler.
    """
    time_from = datetime.datetime.fromtimestamp(
        min(ts for (_, ts, __, ___) in window), tz=datetime.timezone.utc
    ).isoformat()
    time_to = datetime.datetime.fromtimestamp(
        max(ts for (_, ts, __, ___) in window), tz=datetime.timezone.utc
    ).isoformat()
    return time_from, time_to


def _build_used_files_lines(window: List[tuple]) -> Dict[str, tuple[int, int]]:
    used_files: Dict[str, tuple[int, int]] = {}
    for _o, _ts, p, ln in window:
        k = str(p)
        if k in used_files:
            cur_min, cur_max = used_files[k]
            if ln < cur_min:
                cur_min = ln
            if ln > cur_max:
                cur_max = ln
            used_files[k] = (cur_min, cur_max)
        else:
            used_files[k] = (ln, ln)
    return used_files


def extract_relevant(obj: dict) -> Dict[str, Any]:
    """Extraia campos relevantes de um objeto de log para agregação.

    Retorna um dicionário com 'state' e as métricas brutas mapeadas para chaves
    previsíveis usadas pelo agregado e formatadores.

    Nota: historicamente o agregador procurava por `metrics_raw` enquanto o
    emissor atual escreve `metrics` no JSONL. Para ser resiliente a ambas as
    formas, prefira `metrics` e faça fallback para `metrics_raw`.
    """
    # Prefer 'metrics' (escrito pelo feed) e caia para 'metrics_raw' se ausente
    m = obj.get("metrics") or obj.get("metrics_raw") or {}
    # Extrai também os estados individuais se existirem
    return {
        "state_cpu": obj.get("state_cpu"),
        "state_ram": obj.get("state_ram"),
        "state_disk": obj.get("state_disk"),
        "state_ping": obj.get("state_ping"),
        "state_latency": obj.get("state_latency"),
        "state_bytes_sent": obj.get("state_bytes_sent"),
        "state_bytes_recv": obj.get("state_bytes_recv"),
        "cpu_percent": m.get("cpu_percent"),
        "cpu_freq_ghz": m.get("cpu_freq_ghz"),
        "memory_percent": m.get("memory_percent"),
        "memory_used_bytes": m.get("memory_used_bytes"),
        "memory_total_bytes": m.get("memory_total_bytes"),
        "disk_percent": m.get("disk_percent"),
        "disk_used_bytes": m.get("disk_used_bytes"),
        "disk_total_bytes": m.get("disk_total_bytes"),
        "bytes_sent": m.get("bytes_sent"),
        "bytes_recv": m.get("bytes_recv"),
        "ping_ms": m.get("ping_ms"),
        "latency_ms": m.get("latency_ms"),
        "temperature": m.get("temperature"),
        "bytes_sent_human": _human_bytes(m.get("bytes_sent")),
        "bytes_recv_human": _human_bytes(m.get("bytes_recv")),
    }


def _normalize_state(s: Optional[str]) -> Optional[str]:
    """Normalize strings de estado para valores canônicos em maiúsculas.

    Exemplos: 'CRITICAL' ou 'CRIT' -> 'CRITICAL'; 'WARN' -> 'WARNING'.
    Retorna None quando a entrada for falsy.
    """
    if not s:
        return None
    try:
        su = str(s).strip().upper()
    except Exception:
        return None
    if su in ("CRITICAL", "CRIT"):
        return "CRITICAL"
    if su in ("WARN", "WARNING"):
        return "WARNING"
    return su


def aggregate_last_seconds(logs_root: Path, seconds: int = 10) -> Optional[Dict[str, Any]]:
    """Agregue métricas dos últimos `seconds` segundos a partir dos JSONL do dia.

    Retorna um dicionário contendo médias, contagens e metadados, ou None se
    não houver dados válidos. Projetado para ser resiliente a linhas JSON inválidas.
    """
    objs: List[tuple[dict, Path, int]] = list(_iter_jsonl_today(logs_root))
    if not objs:
        return None

    # extrair timestamps e manter itens válidos (defensive unpack)
    items: List[tuple[dict, float, Path, int]] = []
    for entry in objs:
        try:
            o, src_path, src_ln = entry
        except ValueError:
            continue
        ts = extract_epoch(o)
        if ts is not None:
            items.append((o, ts, src_path, src_ln))
    if not items:
        return None

    # janela: do maior timestamp até `seconds` antes
    last_ts = max(ts for (_, ts, __, ___) in items)
    cutoff = last_ts - float(seconds)

    window = [(o, ts, p, ln) for (o, ts, p, ln) in items if cutoff <= ts <= last_ts]
    if not window:
        return None

    n_lines = len(window)

    metric_keys = (
        "cpu_percent",
        "cpu_freq_ghz",
        "memory_percent",
        "memory_used_bytes",
        "memory_total_bytes",
        "disk_percent",
        "disk_used_bytes",
        "disk_total_bytes",
        "bytes_sent",
        "bytes_recv",
        "ping_ms",
        "latency_ms",
        "temperature",
    )

    # Compute averages, counts and per-state counts using helper
    averages, counts, counts_by_state_per_metric, state_counts = _compute_averages_and_counts(window, list(metric_keys))

    # compute state durations using helper
    sorted_window = sorted(window, key=lambda x: x[1])
    state_durations, state_durations_human = _compute_state_durations(sorted_window)

    time_from, time_to = _compute_time_from_to(window)

    result: Dict[str, Any] = {
        "window_seconds": seconds,
        "n_lines": n_lines,
        "time_from": time_from,
        "time_to": time_to,
        "averages": averages,
        "state_counts": state_counts or None,
        "state_durations": state_durations or None,
        "state_durations_human": state_durations_human or None,
        "counts_per_metric": counts,
        "counts_per_metric_by_state": counts_by_state_per_metric,
    }

    # build used files/lines map using helper
    try:
        used_files = _build_used_files_lines(window)
        if used_files:
            result["used_files_lines"] = used_files
    except Exception as exc:
        logging.getLogger(__name__).debug("aggregate used_files_lines build failed: %s", exc, exc_info=True)

    # human readable for bytes averages
    _add_human_bytes(result["averages"])

    _safe_persist_last_time(last_ts=last_ts)

    return result


def _add_human_bytes(averages: Dict[str, Any]) -> None:
    """Adicione campos legíveis (GB) ao dicionário de médias quando aplicável."""
    try:
        if averages.get("bytes_sent") is not None:
            averages["bytes_sent_human"] = _human_bytes(averages["bytes_sent"])
        if averages.get("bytes_recv") is not None:
            averages["bytes_recv_human"] = _human_bytes(averages["bytes_recv"])
    except Exception:
        logging.getLogger(__name__).debug("_add_human_bytes failed", exc_info=True)


def _safe_persist_last_time(last_ts: float) -> None:
    """Persista last_ts em arquivo sem propagar exceções para o chamador.

    Registra em debug se ocorrer falha e segue em modo best-effort.
    """
    try:
        persist_last_time(last_ts=last_ts)
    except Exception as exc:
        logging.getLogger(__name__).debug("persist_last_time failed: %s", exc, exc_info=True)


def format_long_metric_from_aggregate(aggregate: Dict[str, Any]) -> str:
    """Build a long_metric string (multiple lines) from aggregate result.

    Uses formatters._build_long_from_metrics to produce the list of lines,
    then joins them with newlines and returns a single string.
    """
    metrics_src = _build_metrics_src_from_aggregate(aggregate)

    # Delegate to existing formatter to build lines
    try:
        lines = _build_long_from_metrics(metrics_src)
    except Exception:
        # fallback: simple key: value lines
        lines = [f"{k}: {v}" for k, v in metrics_src.items()]

    # decorate metric lines with counts/suffixes
    counts_by_state = aggregate.get("counts_per_metric_by_state") or {}
    out_lines = _decorate_metric_lines(lines, counts_by_state)

    # If used_files_lines present, format into human-friendly lines
    try:
        used = aggregate.get("used_files_lines") if isinstance(aggregate, dict) else None
        if used:
            out_lines.extend(format_used_files_lines(used))
    except Exception as exc:
        logging.getLogger(__name__).debug(
            "format_long_metric_from_aggregate used_files_lines section failed: %s",
            exc,
            exc_info=True,
        )

    return "\n".join(out_lines)


# vulture: ignore
# NOTE: The functions `extract_window_entries`, `get_fixed_log_path` and
# `_format_used_files_lines` were intentionally removed as part of a
# cleanup: their behavior overlapped with other public APIs and they were
# only used by tests. If needed in the future, their implementations can
# be restored from version control.


def _build_metrics_src_from_aggregate(aggregate: Dict[str, Any]) -> Dict[str, Any]:
    """Build the metrics_src dict used by format_long_metric_from_aggregate.

    Copies averages and converts time_to ISO to epoch when possible.
    """
    metrics_src: Dict[str, Any] = {}
    avgs = aggregate.get("averages") or {}
    for k, v in avgs.items():
        metrics_src[k] = v

    ts_iso = aggregate.get("time_to")
    if ts_iso:
        # Delegate parsing to centralized helper to support many timestamp formats
        try:
            from ..system.time_helpers import extract_epoch as _extract_epoch  # local import

            parsed = _extract_epoch({"time_to": ts_iso}) if not isinstance(ts_iso, (int, float)) else float(ts_iso)
            metrics_src["timestamp"] = parsed if parsed is not None else ts_iso
        except Exception:
            metrics_src["timestamp"] = ts_iso

    return metrics_src


def _decorate_metric_lines(lines: List[str], counts_by_state: Dict[str, Any]) -> List[str]:
    """Decorate metric lines with WARNING/CRITICAL suffixes and alignment.

    Preserves the mapping and arrow-decoration behavior from the original
    implementation.
    """

    def _state_suffix_for_metric_key(mkey: str) -> str:
        return _compute_suffix_for_metric_key(counts_by_state, mkey)

    # Mapeamento atualizado: cada prefixo de linha para a chave de métrica,
    # e também para o campo de estado individual correspondente
    mapping = {
        "CPU:": "cpu_percent",
        "RAM:": "memory_used_bytes",
        "Disco:": "disk_used_bytes",
        "Ping:": "ping_ms",
        "Latência:": "latency_ms",
        "Bytes enviados:": "bytes_sent",
        "Bytes recebidos:": "bytes_recv",
    }

    metric_lines_idx = []
    for i, ln in enumerate(lines):
        for prefix in mapping.keys():
            if ln.startswith(prefix):
                metric_lines_idx.append(i)
                break

    max_len = 0
    for i in metric_lines_idx:
        max_len = max(max_len, len(lines[i]))

    out_lines: List[str] = []
    for i, ln in enumerate(lines):
        for prefix, key in mapping.items():
            if ln.startswith(prefix):
                # Use the metric key (e.g. 'cpu_percent') to lookup per-metric
                # state counts. Previously the code passed the state field
                # name (e.g. 'state_cpu') which does not match the keys in
                # counts_per_metric_by_state and prevented suffixes from
                # appearing. Pass `key` so _compute_suffix_for_metric_key
                # finds the correct counts dict.
                suffix = _state_suffix_for_metric_key(key).lstrip()
                target_col = max_len + 3
                current_len = len(ln)
                dash_count = max(1, target_col - current_len)
                deco = " •" + ("-" * dash_count) + ">" + suffix
                ln = ln + deco
                break
        out_lines.append(ln)
    return out_lines


def write_average_log(
    aggregate: Dict[str, Any],
    human_enable: bool = True,
    json_enable: bool = False,
    safe_log_enable: bool = True,
    log: bool = True,
    hourly: bool = True,
    hourly_window_seconds: int = 10,
    name: str = "average_metric",
) -> None:
    """Format aggregate as long_metric and write via system.write_log and to fixed file.

    - Builds the long_metric using `format_long_metric_from_aggregate`.
        - Calls `write_log(name, 'INFO', message, ..., human_enable=..., json_enable=...,
            safe_log_enable=..., log=..., hourly=..., hourly_window_seconds=...)`.
        - Also appends the same human text to a fixed file at `logs/log/{name}.log`.
    """
    human_text = format_long_metric_from_aggregate(aggregate)

    # Delegate safe datestamped write to the logging subsystem which will
    # preserve multiline human text when safe_log_enable=True (see
    # src/system/logs.py change). This centralizes file naming and avoids
    # duplicate datestamped files being created by both subsystems.
    try:
        write_log(
            name=name,
            level="INFO",
            message=human_text,
            extra=None,
            human_enable=bool(human_enable),
            json_enable=json_enable,
            safe_log_enable=safe_log_enable,
            log=log,
            hourly=hourly,
            hourly_window_seconds=hourly_window_seconds,
        )
    except Exception as exc:
        # do not crash if logging subsystem fails; log debug
        logging.getLogger(__name__).debug("write_log failed: %s", exc, exc_info=True)


def _compute_suffix_for_metric_key(counts_by_state: Dict[str, Any], mkey: str) -> str:
    d = counts_by_state.get(mkey) or {}
    warn = int(d.get("WARNING", d.get("WARN", 0) or 0))
    critical = int(d.get("CRITICAL", d.get("CRIT", 0)) or 0)
    if warn > 0 or critical > 0:
        return f" (WARNING={warn} CRITICAL={critical})"
    return ""


def get_last_ts_file(name: str = "last_ts") -> Path:
    """Retorne o Path para o ficheiro last_ts JSON e garanta que o pai exista.

    Se `logs_root` for None, resolve a partir do subsistema de logging para
    que o cache fique sob o mesmo `logs_root` usado por `get_log_paths()`.
    """
    # Cria o arquivo dentro de .cache na raiz do projeto
    project_root = Path(__file__).resolve().parent.parent.parent
    cache_dir = project_root / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{name}.json"


def persist_last_time(last_ts: Optional[float] = None, name: str = "last_ts") -> Path:
    """Persista um JSON único com o último timestamp (epoch) e ISO.

    Substitui o ficheiro com um pequeno objeto JSON. Se `last_ts` for None,
    utiliza o timestamp UTC atual.
    """
    if last_ts is None:
        last_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()

    entry = {
        "last_time": float(last_ts),
        "last_time_iso": datetime.datetime.fromtimestamp(last_ts, tz=datetime.timezone.utc).isoformat(),
    }

    fpath = get_last_ts_file(name=name)
    try:
        with fpath.open("w", encoding="utf-8") as fh:
            json.dump(entry, fh, ensure_ascii=False)
    except PermissionError as exc:
        logging.getLogger(__name__).warning(
            "persist_last_time: permission denied creating %s: %s", fpath, exc, exc_info=True
        )
        # best-effort: try append via write_text as fallback
        try:
            from ..system.log_helpers import write_text

            write_text(fpath, json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            # best-effort fallback: ignore errors when attempting append fallback
            # nosec B110 - intentional swallow: persistence is best-effort here
            pass
    except OSError as exc:
        logging.getLogger(__name__).error("persist_last_time: failed writing %s: %s", fpath, exc, exc_info=True)
    return fpath


def read_last_time(name: str = "last_ts") -> Optional[float]:
    """Leia o ficheiro JSON e retorne o valor numérico `last_time` (epoch) ou None."""
    fpath = get_last_ts_file(name=name)
    if not fpath.exists():
        return None
    try:
        with fpath.open("r", encoding="utf-8") as fh:
            obj = json.load(fh)
        v = obj.get("last_time")
        if v is None:
            return None
        return float(v)
    except (OSError, TypeError, ValueError) as exc:
        logging.getLogger(__name__).error("read_last_time: failed reading %s: %s", fpath, exc, exc_info=True)
        return None


# Auxiliar leve: garante que o arquivo last_ts exista em tempo de execução
def ensure_last_ts_exists(name: str = "last_ts") -> None:
    """Garante existência do arquivo de controle `last_ts` durante execução.

    Faz uma verificação rápida; se o ficheiro não existir, chama
    `persist_last_time()` para criar o arquivo no `logs_root` fornecido
    (ou no root padrão resolvido por `get_last_ts_file`). Projetado para
    ser chamado frequentemente pelo loop sem overhead significativo.
    """
    logger = logging.getLogger(__name__)
    try:
        fpath = get_last_ts_file(name=name)
    except Exception as exc:
        logger.error("ensure_last_ts_exists: falha ao resolver caminho: %s", exc, exc_info=True)
        return

    if not fpath.exists():
        try:
            # persist_last_time cuida de criar o diretório pai quando necessário
            persist_last_time(last_ts=None, name=name)
            logger.debug("ensure_last_ts_exists: criado %s", fpath)
        except Exception as exc:
            logger.error("ensure_last_ts_exists: não foi possível criar %s: %s", fpath, exc, exc_info=True)


def ensure_default_last_ts() -> None:
    """Ensure the default last_ts file exists and contains a non-zero timestamp.

    This function centralizes o que rodava no import. Deve ser chamada pelo entrypoint
    durante o startup para evitar I/O no import.
    """
    try:
        existing = read_last_time()
    except Exception:
        existing = None

    if existing is None or abs(float(existing) - 0.0) <= 1e-9:
        try:
            persist_last_time()
        except Exception as exc:
            logging.getLogger(__name__).debug("persist_last_time on startup init failed: %s", exc, exc_info=True)
            # Persistir timestamp atual (persist_last_time cuida do diretório)
            try:
                persist_last_time()
            except Exception as exc:
                # fallback: log debug but do not raise
                logging.getLogger(__name__).debug("persist_last_time on startup init failed: %s", exc, exc_info=True)
