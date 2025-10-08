from pathlib import Path
from typing import Iterator, Optional, Dict, Any, List
import json
import datetime
import logging
from monitoring.formatters import _build_long_from_metrics
from system.logs import write_log, get_log_paths

# imports kept minimal; avoid unused imports that ruff flags

# do not import iter_jsonl_objects from averages (may be removed); decode JSONL inline


def _iter_jsonl_today(logs_root: Path) -> Iterator[tuple[dict, Path, int]]:
    """Itera objetos JSON válidos do arquivo do dia em possíveis localizações.

    Abre o arquivo candidato e decodifica cada linha JSON (ignora linhas inválidas).
    """

    def _find_candidate_files(root: Path) -> List[Path]:
        t = datetime.date.today().strftime("%Y-%m-%d")
        return [
            root / "logs" / "json" / "monitoring" / f"monitoring-{t}.jsonl",
            root / "logs" / "json" / f"monitoring-{t}.jsonl",
            root / "json" / "monitoring" / f"monitoring-{t}.jsonl",
            root / "json" / f"monitoring-{t}.jsonl",
        ]

    for c in _find_candidate_files(logs_root):
        if not c.exists():
            continue
        try:
            with c.open("r", encoding="utf-8") as fh:
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
                        # yield tuple: (object, file path, line number)
                        yield obj, c, lineno
        except Exception as exc:
            # ignore file read errors and try next candidate (log debug)
            logging.getLogger(__name__).debug("_iter_jsonl_today: failed reading %s: %s", c, exc, exc_info=True)
        return


# --- Extracted helpers for epoch parsing (moved to module level to reduce
# complexity inside _extract_epoch)
def _epoch_from_numeric(v) -> Optional[float]:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    # heurística: valores maiores que ~1e12 provavelmente são ms
    if n > 1e12:
        return n / 1000.0
    return n


def _parse_date_string(s: str) -> Optional[float]:
    if not isinstance(s, str):
        return None
    t = s.strip()
    if not t:
        return None
    # numeric-looking string
    try:
        n = float(t)
        if n > 1e12:
            return n / 1000.0
        return n
    except (TypeError, ValueError):
        pass

    # normalize trailing Z
    if t.endswith("Z"):
        t2 = t[:-1] + "+00:00"
    else:
        t2 = t

    # try ISO
    try:
        dt = datetime.datetime.fromisoformat(t2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.timestamp()
    except ValueError:
        pass

    # common formats
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.datetime.strptime(t, fmt)
            dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue

    return None


def _parse_epoch_from_value(v) -> Optional[float]:
    if v is None:
        return None
    # numeric (or numeric-like)
    n = _epoch_from_numeric(v)
    if n is not None:
        return n
    # strings
    if isinstance(v, str):
        s = _parse_date_string(v)
        if s is not None:
            return s
    return None


def _scan_keys_in_obj(container, depth: int = 3) -> Optional[float]:
    if depth < 0 or container is None:
        return None
    if not isinstance(container, (dict, list)):
        return _parse_epoch_from_value(container)
    keys_to_match = {"ts", "timestamp", "time", "date", "last_time", "created_at", "data/hora"}
    # If container is a dict: inspect direct keys, likely subtrees and shallow values
    if isinstance(container, dict):
        cand = _scan_direct_keys(container, keys_to_match)
        if cand is not None:
            return cand
        for subtree in _iter_likely_subtrees(container):
            cand = _scan_subtree_for_timestamp(subtree, depth - 1)
            if cand is not None:
                return cand
        cand = _scan_values_shallow(container, depth - 1)
        if cand is not None:
            return cand
        return None

    # container is a list: delegate to helper that returns the best timestamp
    return _scan_list_for_keys(container, depth - 1)


def _scan_list_for_keys(lst: list, depth: int) -> Optional[float]:
    """Scan a list for timestamp-like entries and prefer the latest found."""
    best = None
    for item in lst:
        cand = _scan_keys_in_obj(item, depth)
        if cand is not None:
            if best is None or cand > best:
                best = cand
    return best


def _scan_direct_keys(container: dict, keys_to_match: set) -> Optional[float]:
    """Check direct keys in a dict for timestamp-like entries."""
    for k, v in container.items():
        try:
            ks = str(k).lower()
        except Exception:
            ks = None
        if ks and ks in keys_to_match:
            cand = _parse_epoch_from_value(v)
            if cand is not None:
                return cand
    return None


def _iter_likely_subtrees(container: dict) -> Iterator[Any]:
    """Yield likely subtrees for timestamp scanning from a container dict."""
    for k in ("metrics_raw", "meta", "data", "payload", "event", "events"):
        if k in container:
            yield container.get(k)


def _scan_values_shallow(container: dict, depth: int) -> Optional[float]:
    """Shallow-scan all values of a container and recurse limited by depth."""
    for v in container.values():
        if isinstance(v, (dict, list)):
            cand = _scan_keys_in_obj(v, depth)
            if cand is not None:
                return cand
    return None


def _extract_epoch(obj: dict) -> Optional[float]:
    """Tenta extrair um timestamp epoch (float) de um objeto de log.

    Procura em (metrics_raw.timestamp), ts, timestamp ou em campos legíveis
    como 'Data/hora' no formato YYYY-MM-DD HH:MM:SS ou ISO.
    Retorna None se não for possível obter uma epoch válida.
    """
    # Monolithic implementation with local helpers. Preserves existing priority
    # while adding controlled scans and centralized parsing logic.

    # Use module-level parsing helpers (extracted) to keep this function small.
    # preserve existing priority and behavior by delegating to those helpers.

    # preserve existing priority and behavior
    # 1) metrics_raw.timestamp (numeric or string)
    m = obj.get("metrics_raw") or {}
    if isinstance(m, dict) and (v := m.get("timestamp")) is not None:
        n = _parse_epoch_from_value(v)
        if n is not None:
            return n

    # 2) top-level numeric fields or strings
    for key in ("ts", "timestamp"):
        if key in obj:
            v = obj.get(key)
            n = _parse_epoch_from_value(v)
            if n is not None:
                return n
    # 3) Data/hora-like localized keys
    n = _check_localized_date_keys(obj)
    if n is not None:
        return n

    # 4) limited-scope scan in likely subtrees (metrics_raw, meta, events)
    for subtree in (obj.get("metrics_raw"), obj.get("meta"), obj.get("events")):
        if subtree is not None:
            n = _scan_keys_in_obj(subtree, depth=3)
            if n is not None:
                return n

    # 5) fallback: broader DFS scan across the whole object (no depth limit)
    n = _dfs_scan_for_timestamp(obj)
    return n


def _check_localized_date_keys(obj: dict) -> Optional[float]:
    """Check known localized/date-ish top-level keys for parseable timestamps."""
    for key in ("Data/hora", "Data/Hora", "data/hora", "date", "Date"):
        if key in obj:
            v = obj.get(key)
            n = _parse_epoch_from_value(v)
            if n is not None:
                return n
    return None


def _dfs_scan_for_timestamp(node: Any) -> Optional[float]:
    """DFS scan of an object tree to find timestamp-like keys/values.

    Kept as a separate helper to reduce complexity in _extract_epoch.
    """
    stack: list[Any] = [node]
    while stack:
        nd = stack.pop()
        if not isinstance(nd, (dict, list)):
            continue
        if isinstance(nd, dict):
            n = _dfs_scan_dict(nd)
            if n is not None:
                return n
            continue
        # nd is a list
        n = _dfs_scan_list(nd)
        if n is not None:
            return n
    return None


def _dfs_scan_dict(d: dict) -> Optional[float]:
    """Scan a dict node for timestamp-like keys/values during DFS."""
    keys_to_match = {"ts", "timestamp", "time", "date", "last_time", "created_at", "data/hora"}
    for k, v in d.items():
        try:
            ks = str(k).lower()
        except Exception:
            ks = None
        if ks and ks in keys_to_match:
            n = _parse_epoch_from_value(v)
            if n is not None:
                return n
        if isinstance(v, (dict, list)):
            # enqueue for further DFS handled in the main loop of _dfs_scan_for_timestamp
            # return None here so caller loops and handles lists/dicts centrally
            return None
    return None


def _dfs_scan_list(lst: list) -> Optional[float]:
    """Scan a list node for dict/list children during DFS."""
    for item in lst:
        if isinstance(item, (dict, list)):
            n = _dfs_scan_for_timestamp(item)
            if n is not None:
                return n
    return None


def _scan_subtree_for_timestamp(subtree: Any, depth: int) -> Optional[float]:
    """Scan a subtree (list or dict) and return the best timestamp found.

    This helper delegates to _scan_keys_in_obj as appropriate. Extracted to
    simplify _scan_keys_in_obj.
    """
    if isinstance(subtree, list):
        best = None
        for item in subtree:
            cand = _scan_keys_in_obj(item, depth - 1)
            if cand is not None:
                if best is None or cand > best:
                    best = cand
        return best
    return _scan_keys_in_obj(subtree, depth)


def _human_bytes(b: Optional[float]) -> Optional[str]:
    if b is None:
        return None
    try:
        b = float(b)
    except Exception:
        return None
    # present as GB with two decimals when appropriate
    gb = b / (1024**3)
    return f"{gb:.2f} GB"


def _compute_averages_and_counts(window: List[tuple], metric_keys: List[str]):
    """Compute sums, counts, averages and counts_by_state for a given window.

    Returns (averages, counts, counts_by_state_per_metric, state_counts).
    """
    sums: Dict[str, float] = dict.fromkeys(metric_keys, 0.0)
    counts: Dict[str, int] = dict.fromkeys(metric_keys, 0)
    counts_by_state_per_metric: Dict[str, Dict[str, int]] = {k: {} for k in metric_keys}
    state_counts: Dict[str, int] = {}

    for o, _ts, _p, _ln in window:
        rel = extract_relevant(o)
        st = _normalize_state(rel.get("state"))
        if st is not None:
            state_counts[st] = state_counts.get(st, 0) + 1

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
            if st is not None:
                d = counts_by_state_per_metric.get(k) or {}
                d[st] = d.get(st, 0) + 1
                counts_by_state_per_metric[k] = d

    averages: Dict[str, Optional[float]] = {}
    for k in metric_keys:
        cnt = counts.get(k, 0) or 0
        if cnt == 0:
            averages[k] = None
        else:
            averages[k] = sums.get(k, 0.0) / float(cnt)

    return averages, counts, counts_by_state_per_metric, state_counts


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

    def _format_duration(s: float) -> str:
        try:
            secs = int(round(float(s)))
        except Exception:
            return "0:00:00"
        return str(datetime.timedelta(seconds=secs))

    state_durations_human: Dict[str, str] = (
        {k: _format_duration(v) for k, v in state_durations.items()} if state_durations else {}
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


# canonical metric keys used across aggregation
METRIC_KEYS = (
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


def _collect_items_from_objs(objs: List[tuple]) -> List[tuple]:
    """Collect (obj, ts, path, lineno) items from iterator results, defensive unpack.

    Extracts epoch using _extract_epoch and skips malformed entries.
    """
    items: List[tuple[dict, float, Path, int]] = []
    for entry in objs:
        try:
            o, src_path, src_ln = entry
        except (ValueError, TypeError):
            # defensive: skip malformed iterator entries
            continue
        ts = _extract_epoch(o)
        if ts is not None:
            items.append((o, ts, src_path, src_ln))
    return items


def _select_window(items: List[tuple], seconds: int) -> List[tuple]:
    """Return filtered window of items whose ts is within last `seconds` of max timestamp.

    Items are tuples (o, ts, path, lineno).
    """
    if not items:
        return []
    last_ts = max(ts for (_, ts, __, ___) in items)
    cutoff = last_ts - float(seconds)
    window = [(o, ts, p, ln) for (o, ts, p, ln) in items if cutoff <= ts <= last_ts]
    return window


def extract_relevant(obj: dict) -> Dict[str, Any]:
    """Extrai os campos relevantes de um objeto de log.

    Retorna um dicionário com: state e as métricas listadas pelo usuário.
    """
    m = obj.get("metrics_raw") or {}
    return {
        "state": obj.get("state"),
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
    """Normalize state strings to canonical uppercase values.

        Maps common variants to canonical names used in counting/formatting.

    Examples:
            'CRITIC' or 'CRIT' -> 'CRITICAL'
            'WARN' -> 'WARNING'
    Returns None if input is falsy.

    """
    if not s:
        return None
    try:
        su = str(s).strip().upper()
    except Exception:
        return None
    if su in ("CRITIC", "CRIT", "CRITICAL"):
        return "CRITICAL"
    if su in ("WARN", "WARNING"):
        return "WARNING"
    return su


def aggregate_last_seconds(logs_root: Path, seconds: int = 10) -> Optional[Dict[str, Any]]:
    """Aggregate metrics from the last `seconds` seconds available in today's JSONL.

    Returns a dict with averages, counts and metadata or None when no data.
    Designed to be lightweight and robust to malformed lines.
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
        ts = _extract_epoch(o)
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

    _safe_persist_last_time(last_ts=last_ts, logs_root=logs_root)

    return result


def _add_human_bytes(averages: Dict[str, Any]) -> None:
    """Add human-readable bytes fields to averages dict when present."""
    try:
        if averages.get("bytes_sent") is not None:
            averages["bytes_sent_human"] = _human_bytes(averages["bytes_sent"])
        if averages.get("bytes_recv") is not None:
            averages["bytes_recv_human"] = _human_bytes(averages["bytes_recv"])
    except Exception:
        logging.getLogger(__name__).debug("_add_human_bytes failed", exc_info=True)


def _safe_persist_last_time(last_ts: float, logs_root: Path | None) -> None:
    """Persist last_ts but never raise to caller; log debug on failure."""
    try:
        persist_last_time(last_ts=last_ts, logs_root=logs_root)
    except Exception as exc:
        logging.getLogger(__name__).debug("persist_last_time failed: %s", exc, exc_info=True)


def extract_window_entries(logs_root: Path, seconds: int = 10) -> List[Dict[str, Any]]:
    """Retorna uma lista com os dados relevantes extraídos de todas as linhas.

    no intervalo de `seconds` segundos a partir da última linha disponível.

    Cada item da lista contém as chaves retornadas por `extract_relevant` mais
    `timestamp_epoch` e `timestamp_iso`.
    """
    objs: List[tuple[dict, Path, int]] = list(_iter_jsonl_today(logs_root))
    if not objs:
        return []

    items: List[tuple[dict, float, Path, int]] = []
    for entry in objs:
        try:
            o, p, ln = entry
        except ValueError:
            # skip malformed iterator entries
            continue
        ts = _extract_epoch(o)
        if ts is not None:
            items.append((o, ts, p, ln))
    if not items:
        return []

    last_ts = max(ts for (_, ts, __, ___) in items)
    cutoff = last_ts - float(seconds)

    window = [(o, ts, p, ln) for (o, ts, p, ln) in items if cutoff <= ts <= last_ts]
    if not window:
        return []

    out: List[Dict[str, Any]] = []
    for o, ts, p, ln in window:
        r = extract_relevant(o)
        r["timestamp_epoch"] = ts
        r["timestamp_iso"] = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()
        # also expose source metadata for debugging if needed
        r["_src_file"] = str(p)
        r["_src_line"] = int(ln)
        out.append(r)

    return out


def get_fixed_log_path(name: str = "average_metric") -> Path:
    """Return the fixed log path logs/log/{name}.log using get_log_paths()."""
    lp = get_log_paths()
    return lp.log_dir / f"{name}.log"


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
            out_lines.extend(_format_used_files_lines(used))
    except Exception as exc:
        logging.getLogger(__name__).debug(
            "format_long_metric_from_aggregate used_files_lines section failed: %s",
            exc,
            exc_info=True,
        )

    return "\n".join(out_lines)


def _format_used_files_lines(used: Dict[str, Any]) -> List[str]:
    """Format a used_files_lines dict into a list of human-readable lines.

    Expects a mapping of path->(min_line, max_line). Returns list like:
    ['','Linhas usadas:', 'file1 linhas 12 a 24', 'file2 linha 50']
    """
    out: List[str] = ["", "Linhas usadas:"]
    for k in sorted(used.keys()):
        try:
            rng = used.get(k)
        except (AttributeError, TypeError):
            continue
        if not isinstance(rng, (list, tuple)) or len(rng) < 2:
            continue
        a, b = int(rng[0]), int(rng[1])
        try:
            fname = Path(k).name
        except Exception:
            fname = str(k)
        if a == b:
            out.append(f"{fname} linha {a}")
        else:
            out.append(f"{fname} linhas {a} a {b}")
    return out


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
        try:
            dt = datetime.datetime.fromisoformat(ts_iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            metrics_src["timestamp"] = dt.timestamp()
        except Exception:
            metrics_src["timestamp"] = ts_iso

    return metrics_src


def _decorate_metric_lines(lines: List[str], counts_by_state: Dict[str, Any]) -> List[str]:
    """Decorate metric lines with WARNING/CRITICAL suffixes and alignment.

    Preserves the mapping and arrow-decoration behavior from the original
    implementation.
    """

    def _state_suffix_for_metric_key(mkey: str) -> str:
        d = counts_by_state.get(mkey) or {}
        warn = int(d.get("WARNING", d.get("WARN", 0) or 0))
        critical = int(d.get("CRITICAL", d.get("CRITIC", d.get("CRIT", 0) or 0)) or 0)
        return f" (WARNING={warn} CRITICAL={critical})"

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
            human_enable=True,
            json_enable=json_enable,
            safe_log_enable=safe_log_enable,
            log=log,
            hourly=hourly,
            hourly_window_seconds=hourly_window_seconds,
        )
    except Exception as exc:
        # do not crash if logging subsystem fails; log debug
        logging.getLogger(__name__).debug("write_log failed: %s", exc, exc_info=True)


# store last timestamp in a single JSON under logs/.cache/last_ts.json
# previously this used Path('logs') / '.cache' which, when combined with a
# provided logs_root resulted in duplicate 'logs/logs/.cache'. Use a relative
# '.cache' directory so get_last_ts_file(logs_root) resolves to
# <logs_root>/.cache/last_ts.json as intended.
LAST_TS_DIR = Path(".cache")


def get_last_ts_file(name: str = "last_ts", logs_root: Path | None = None) -> Path:
    """Return the Path to the last_ts JSON file and ensure parent exists.

    If `logs_root` is None, resolve it from the logging subsystem so the
    cache lives under the same logs root used by `get_log_paths()`.
    """
    if logs_root is None:
        lp = get_log_paths()
        logs_root = lp.root
    path = Path(logs_root) / LAST_TS_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{name}.json"


def persist_last_time(last_ts: Optional[float] = None, name: str = "last_ts", logs_root: Path | None = None) -> Path:
    """Persist a single JSON file with the last_time (epoch) and ISO.

    Overwrites the file with a small JSON object. If last_ts is None, uses
    current UTC timestamp.
    """
    if last_ts is None:
        last_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()

    entry = {
        "last_time": float(last_ts),
        "last_time_iso": datetime.datetime.fromtimestamp(last_ts, tz=datetime.timezone.utc).isoformat(),
    }

    fpath = get_last_ts_file(name=name, logs_root=logs_root)
    with fpath.open("w", encoding="utf-8") as fh:
        json.dump(entry, fh, ensure_ascii=False)
    return fpath


def read_last_time(name: str = "last_ts", logs_root: Path | None = None) -> Optional[float]:
    """Read the JSON file and return the numeric last_time (epoch) or None."""
    fpath = get_last_ts_file(name=name, logs_root=logs_root)
    if not fpath.exists():
        return None
    try:
        with fpath.open("r", encoding="utf-8") as fh:
            obj = json.load(fh)
        v = obj.get("last_time")
        if v is None:
            return None
        return float(v)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


# Auxiliar leve: garante que o arquivo last_ts exista em tempo de execução
def ensure_last_ts_exists(name: str = "last_ts", logs_root: Path | None = None) -> None:
    """Garante existência do arquivo de controle `last_ts` durante execução.

    Faz uma verificação rápida; se o ficheiro não existir, chama
    `persist_last_time()` para criar o arquivo no `logs_root` fornecido
    (ou no root padrão resolvido por `get_last_ts_file`). Projetado para
    ser chamado frequentemente pelo loop sem overhead significativo.
    """
    logger = logging.getLogger(__name__)
    try:
        fpath = get_last_ts_file(name=name, logs_root=logs_root)
    except Exception as exc:
        logger.debug("ensure_last_ts_exists: falha ao resolver caminho: %s", exc, exc_info=True)
        return

    if not fpath.exists():
        try:
            # persist_last_time cuida de criar o diretório pai quando necessário
            persist_last_time(last_ts=None, name=name, logs_root=logs_root)
            logger.debug("ensure_last_ts_exists: criado %s", fpath)
        except Exception as exc:
            logger.debug("ensure_last_ts_exists: não foi possível criar %s: %s", fpath, exc, exc_info=True)


# Garantir que o arquivo default exista ao importar o módulo.
# Se faltar ou contiver last_time = 0.0 (criado por versões antigas), regravar
# com o timestamp atual para evitar janelas inválidas.
try:
    _default_file = get_last_ts_file()
    try:
        existing = read_last_time()
    except Exception:
        existing = None

    if existing is None or float(existing) == 0.0:
        # Persistir timestamp atual (persist_last_time cuida do diretório)
        try:
            persist_last_time()
        except Exception as exc:
            # fallback: não falhar na importação
            logging.getLogger(__name__).debug("persist_last_time on import-time init failed: %s", exc, exc_info=True)
except Exception as exc:
    # não falhar na importação caso algo dê errado; log debug
    logging.getLogger(__name__).debug("post-import last_ts init failed: %s", exc, exc_info=True)
