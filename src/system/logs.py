"""Subsistema de logs: rotação, compressão e persistência.

Fornece helpers de nível superior para escrita de logs,
rotação, compressão e limpeza de arquivos de archive.
"""

import os

# errno not needed after removing local _ensure_dir_writable
import logging

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .log_helpers import (
    ROTATING_SUFFIX,
    archive_file_is_old,
    build_human_line,
    build_json_entry,
    format_date_for_log,
    normalize_message_for_human,
    sanitize_log_name,
    try_compress_rotating,
    try_rotate_file,
    write_json,
    write_text,
    ensure_dir_writable,
)

logger = logging.getLogger(__name__)

# ========================
# 0. Configuração padrão
# ========================

_raw_log_root = os.getenv("MONITORING_LOG_ROOT", "logs")
if isinstance(_raw_log_root, str):
    _raw_log_root = _raw_log_root.strip()
else:
    _raw_log_root = "logs"

if _raw_log_root == "Logs":
    LOG_ROOT = "logs"
else:
    LOG_ROOT = _raw_log_root or "logs"

DEBUG_LOG_FILENAME = "debug_log"


# ========================
# 1. Diretórios e Paths
# ========================


@dataclass(frozen=True)
# Representa os diretórios usados pelo subsistema de logs; alimenta demais helpers de I/O
class LogPaths:
    """Agrupa caminhos usados pelo subsistema de logging.

    Contém os diretórios root, log, json, archive e debug usados por
    funções de escrita, rotação e limpeza.
    """

    root: Path
    log_dir: Path
    json_dir: Path
    archive_dir: Path
    debug_dir: Path
    cache_dir: Path

    def __iter__(self):
        """Iterador simples que retorna tupla com os principais paths."""
        return iter((self.root, self.log_dir, self.json_dir, self.archive_dir))


def get_log_paths(root: str | Path | None = None) -> LogPaths:
    """Resolve raiz de logs e garante diretórios criados e graváveis.

    Retorna um objeto `LogPaths` com diretórios preparados para escrita e
    leitura pelos subsistemas de logging e archive.
    """
    try:
        # Prefer caller-provided root, then environment variable, then module-level LOG_ROOT
        env_root = os.getenv("MONITORING_LOG_ROOT")
        candidate = root if root else (env_root if env_root is not None else LOG_ROOT)
        log_root = Path(candidate)
    except Exception as exc:
        logger.debug("get_log_paths: falha ao resolver root: %s", exc, exc_info=True)
        project_root = Path(__file__).resolve().parents[2]
        log_root = project_root / "logs"

    # ensure_dir_writable returns bool; call for side-effects and keep Path values
    ensure_dir_writable(log_root)
    log_dir = log_root / "log"
    ensure_dir_writable(log_dir)
    json_dir = log_root / "json"
    ensure_dir_writable(json_dir)
    archive_dir = log_root / "archive"
    ensure_dir_writable(archive_dir)
    debug_dir = log_root / "debug"
    ensure_dir_writable(debug_dir)
    cache_dir = log_root / ".cache"
    ensure_dir_writable(cache_dir)

    return LogPaths(log_root, log_dir, json_dir, archive_dir, debug_dir, cache_dir)


# Gera o nome base para arquivos de log; consumido por write_log
def _resolve_filename(name: str, safe_log_enable: bool) -> str:
    """Gera nome base de arquivo de log com sufixo seguro e data.

    Inclui normalização do nome e sufixo `_safe` quando solicitado.
    """
    default = DEBUG_LOG_FILENAME
    base = sanitize_log_name(name or default, default)
    if safe_log_enable:
        base = f"{base}_safe"
    date_str = format_date_for_log(None)
    return f"{base}-{date_str}"


# Normaliza entradas de mensagem; usado por write_log
def _normalize_messages(message) -> list:
    """Aceita string única, lista ou tupla e retorna lista.

    Garante que a lógica que itera mensagens sempre trabalhe com lista.
    """
    if isinstance(message, (list, tuple)):
        return list(message)
    return [message]


# Normaliza o campo extra para uma lista do tamanho requerido; usado por write_log
def _normalize_extras(extra, count: int) -> list:
    """Normaliza extras para lista de tamanho fixo.

    Aceita dict (replicado), lista/tupla ou None; garante comprimento `count`.
    """
    if extra is None:
        return [None] * count
    if isinstance(extra, dict):
        return [extra] * count
    if isinstance(extra, (list, tuple)):
        lst = list(extra)
        if len(lst) < count:
            lst.extend([None] * (count - len(lst)))
        return lst
    return [extra] * count


# ========================
# 3. Escrita de Logs
# ========================


# Escreve mensagens em .log e .jsonl; alimenta análise e ingestão
def write_log(
    name: str,
    level: str,
    message: str | list[str],
    extra: dict | list[dict] | None = None,
    human_enable: bool = False,
    json_enable: bool = True,
    safe_log_enable: bool = False,
    log: bool = True,
    hourly: bool = False,
    hourly_window_seconds: int = 3600,
) -> None:
    """Grava mensagens em arquivo texto e/ou jsonl.

    Recebe uma ou várias mensagens e as escreve em formato humano (texto)
    e/ou em formato estruturado (jsonl) conforme flags fornecidas.
    """
    filename = _resolve_filename(name, safe_log_enable)

    messages = _normalize_messages(message)
    extras_list = _normalize_extras(extra, len(messages))

    lp = get_log_paths()
    plain_path = lp.log_dir / f"{filename}.log"
    jsonl_path = lp.json_dir / f"{filename}.jsonl"

    for idx, msg in enumerate(messages):
        ts = datetime.now(timezone.utc).isoformat()

        # Preserve multi-line human messages for the hourly summary log or
        # when writing to a safe file. Historically the normalize step
        # flattened newlines; when writing the canonical dated `_safe` files
        # we want to preserve the original multiline human text.
        if human_enable and (name == "monitoring-hourly" or safe_log_enable) and isinstance(msg, str):
            human_msg = msg
        else:
            human_msg = normalize_message_for_human(msg)

        if human_enable:
            _perform_human_write(
                lp,
                plain_path,
                name,
                level,
                human_msg,
                extras_list[idx],
                hourly,
                hourly_window_seconds,
                log,
            )

        if json_enable:
            per_extra = extras_list[idx]
            _perform_json_write(jsonl_path, ts, level, msg, per_extra)


# Auxiliar de write_log: decide se a escrita humana é permitida pela janela hourly
def _hourly_allows_write(lp: LogPaths, name: str, hourly: bool, hourly_window_seconds: int) -> bool:
    """Verifica se a janela 'hourly' permite escrita.

    Retorna True quando não em modo hourly ou quando a janela de tempo
    desde a última escrita excede `hourly_window_seconds`.
    """
    if not hourly:
        return True
    try:
        key = sanitize_log_name(name, name)
        cache_dir = lp.cache_dir
        ts_path = cache_dir / f".last_human_{key}.ts"
        now_int = int(time.time())
        if ts_path.exists():
            try:
                with open(ts_path, "r", encoding="utf-8") as f:
                    last = int(f.read().strip() or 0)
            except (OSError, ValueError):
                last = 0
            return (now_int - last) >= int(hourly_window_seconds)
        return True
    except Exception as exc:
        logger.debug("_hourly_allows_write: erro ao verificar hourly: %s", exc, exc_info=True)
        return True


# Auxiliar de write_log: escreve linha humana em .log e atualiza timestamp hourly
def _perform_human_write(
    lp: LogPaths,
    plain_path: Path,
    name: str,
    level: str,
    human_msg: str,
    extra: dict | None,
    hourly: bool,
    hourly_window_seconds: int,
    log: bool,
) -> None:
    """Executa a escrita humana em arquivo, respeitando flags e janela hourly.

    Atualiza arquivo de timestamp para controlar gravações `hourly`.
    """
    if not log and not hourly:
        logger.debug("human write suprimido (log=False e hourly=False)")
        return

    if _hourly_allows_write(lp, name, hourly, hourly_window_seconds):
        human_line = build_human_line(format_date_for_log(None), level, human_msg, extra)
        write_text(plain_path, human_line)
        if hourly:
            try:
                ts_file = lp.cache_dir / (f".last_human_{sanitize_log_name(name, name)}.ts")
                with open(ts_file, "w", encoding="utf-8") as f:
                    f.write(str(int(time.time())))
            except Exception as exc:
                logger.debug("_perform_human_write: não foi possível escrever hourly ts: %s", exc, exc_info=True)
    else:
        logger.debug("human write ignorado pela janela hourly")


# Auxiliar de write_log: constrói e grava um objeto JSON em jsonl para ingestão
def _perform_json_write(jsonl_path: Path, ts: str, level: str, msg, extra: dict | None) -> None:
    """Constrói o objeto JSON e delega para write_json.

    Mantém formato compatível com consumidores de métricas/ingestão.
    """
    # Avoid embedding human-oriented summaries in the canonical JSON feed.
    # Keep metrics and other machine-readable keys only.
    safe_extra = None
    if isinstance(extra, dict):
        safe_extra = {k: v for k, v in extra.items() if k not in ("summary_short", "summary_long")}
    json_obj = build_json_entry(ts, level, msg, safe_extra)
    write_json(jsonl_path, json_obj)


# Retorna o caminho do arquivo de debug do dia; usado por debug logging
def get_debug_file_path() -> Path:
    """Retorna caminho do arquivo de debug diário.

    Nomeia o arquivo com a data atual no diretório de debug.
    """
    date_str = format_date_for_log(None)
    filename = f"debug_log-{date_str}.txt"
    return get_log_paths().debug_dir / filename


# Auxiliar do loop: verifica e restabelece diretórios de logs se necessários
def ensure_log_dirs_exist(root: str | Path | None = None) -> None:
    """Garante existência dos diretórios de logs e recria se faltarem.

    Faz checagens leves (Path.exists()) e só escala para a criação completa
    chamando a rotina de inicialização quando um caminho estiver ausente.
    Projetada para ser chamada frequentemente pelo loop sem overhead.
    """
    try:
        # resolve candidate root (do not call get_log_paths() yet)
        log_root = Path(root) if root else Path(LOG_ROOT)
    except Exception:
        return

    # list of expected directories under the root
    expected = (
        log_root,
        log_root / "log",
        log_root / "json",
        log_root / "archive",
        log_root / "debug",
    )

    for p in expected:
        # cheap check; if any missing, force resolution/creation via get_log_paths
        if not p.exists():
            try:
                # this will create the directories via _ensure_dir_writable
                get_log_paths(root)
            except Exception as exc:
                logger.debug("ensure_log_dirs_exist: failed to recreate %s: %s", p, exc, exc_info=True)
            break


# ========================
# 4. Rotação e Limpeza
# ========================


def rotate_logs(day_secs: int | None = None, week_secs: int | None = None) -> None:
    """Rotaciona logs para archive."""
    lp = get_log_paths()
    log_dir = lp.log_dir
    json_dir = lp.json_dir
    archive_dir = lp.archive_dir

    if day_secs is None:
        day_secs = 24 * 60 * 60
    if week_secs is None:
        week_secs = 7 * day_secs

    patterns = (
        (json_dir, "*.jsonl", ".jsonl.gz"),
        (log_dir, "*.log", ".log.gz"),
    )
    for src_dir, glob_pat, gz_suffix in patterns:
        for p in sorted(src_dir.glob(glob_pat)):
            try_rotate_file(p, archive_dir, gz_suffix, day_secs, week_secs)


def compress_old_logs(day_secs: int | None = None, week_secs: int | None = None) -> None:
    """Comprime arquivos rotativos antigos."""
    archive_dir = get_log_paths().archive_dir
    if not archive_dir.exists():
        return

    if day_secs is None:
        day_secs = 24 * 60 * 60
    if week_secs is None:
        week_secs = 7 * day_secs

    for rotating in sorted(archive_dir.glob(f"*{ROTATING_SUFFIX}")):
        try_compress_rotating(rotating, archive_dir, day_secs, week_secs)


def safe_remove(retention_days: int = 7, safe_retention_days: int | None = 30) -> None:
    """Remove arquivos antigos do archive."""
    archive_dir = get_log_paths().archive_dir
    if not archive_dir.exists():
        return

    now_ts = datetime.now(timezone.utc).timestamp()
    patterns = ["*.jsonl.gz", "*.log.gz", f"*{ROTATING_SUFFIX}"]

    for pat in patterns:
        for p in sorted(archive_dir.glob(pat)):
            rd = safe_retention_days if ("_safe" in p.name and safe_retention_days is not None) else retention_days
            if not archive_file_is_old(p, now_ts, rd):
                continue
            try:
                p.unlink()
                logger.info("safe_remove: removed %s", p)
            except Exception as exc:
                logger.error("safe_remove: falha ao remover %s: %s", p, exc, exc_info=True)
