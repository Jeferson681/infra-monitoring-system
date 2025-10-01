"""Subsistema de logs: rotação, compressão e persistência."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from system.log_helpers import (
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
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LogPaths:
    """Caminhos usados pelo subsistema de logging.

    Contém os diretórios raiz, log, json, archive e debug usados pelas
    operações de escrita e rotação.
    """

    root: Path
    log_dir: Path
    json_dir: Path
    archive_dir: Path
    debug_dir: Path

    def __iter__(self):
        """Permite desempacotar compatível com código legado.

        Retorna um iterador com (root, log_dir, json_dir, archive_dir).
        """
        return iter((self.root, self.log_dir, self.json_dir, self.archive_dir))


def get_log_paths(root: str | Path | None = None) -> LogPaths:
    """Retorna os caminhos de logs e garante que os diretórios existem.

    Usa config.settings.LOG_ROOT quando disponível; caso contrário usa
    <project_root>/logs. A função garante que os subdiretórios existam.
    """
    if root is not None:
        log_root = Path(root)
    else:
        try:
            from config.settings import LOG_ROOT  # type: ignore

            log_root = Path(LOG_ROOT)
        except Exception:
            project_root = Path(__file__).resolve().parents[2]
            log_root = project_root / "logs"

    log_dir = log_root / "log"
    json_dir = log_root / "json"
    archive_dir = log_root / "archive"
    debug_dir = log_root / "debug"

    for d in (log_root, log_dir, json_dir, archive_dir, debug_dir):
        d.mkdir(parents=True, exist_ok=True)

    return LogPaths(
        log_root,
        log_dir,
        json_dir,
        archive_dir,
        debug_dir,
    )


def rotate_logs() -> None:
    """Rotaciona e comprime ficheiros .log e .jsonl antigos para archive."""
    lp = get_log_paths()
    log_dir = lp.log_dir
    json_dir = lp.json_dir
    archive_dir = lp.archive_dir

    day_secs = 24 * 60 * 60
    week_secs = 7 * day_secs

    patterns = (
        (json_dir, "*.jsonl", ".jsonl.gz"),
        (log_dir, "*.log", ".log.gz"),
    )
    for src_dir, glob_pat, gz_suffix in patterns:
        for p in sorted(src_dir.glob(glob_pat)):
            try_rotate_file(p, archive_dir, gz_suffix, day_secs, week_secs)


def compress_old_logs() -> None:
    """Comprime ficheiros '.rotating' pendentes no diretório de archive."""
    archive_dir = get_log_paths().archive_dir
    if not archive_dir.exists():
        return

    day_secs = 24 * 60 * 60
    week_secs = 7 * day_secs

    for rotating in sorted(archive_dir.glob(f"*{ROTATING_SUFFIX}")):
        try_compress_rotating(rotating, archive_dir, day_secs, week_secs)


def safe_remove(retention_days: int = 7, safe_retention_days: int | None = 30) -> None:
    """Remove ficheiros de archive mais antigos que a retenção configurada."""
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
                logger.warning("safe_remove: failed to remove %s: %s", p, exc)


def get_debug_file_path() -> Path:
    """Retorna o caminho do ficheiro debug para hoje (<root>/debug/debug_log-YYYY-MM-DD.txt)."""
    base_name = "debug_log"
    date_str = format_date_for_log(None)
    filename = f"{base_name}-{date_str}.txt"
    return get_log_paths().debug_dir / filename


def _resolve_filename(name: str, safe_log_enable: bool) -> str:
    """Resolve o nome base do ficheiro de log adicionando data e sufixos.

    Se `safe_log_enable` for True adiciona o sufixo '_safe' antes da data.
    Usa `config.settings.DEBUG_LOG_FILENAME` como valor por defeito quando
    disponível.
    """
    try:
        from config.settings import DEBUG_LOG_FILENAME

        default = DEBUG_LOG_FILENAME
    except Exception:
        default = "debug_log"

    base = sanitize_log_name(name or default, default)
    if safe_log_enable:
        base = f"{base}_safe"
    date_str = format_date_for_log(None)
    return f"{base}-{date_str}"


def _normalize_messages(message) -> list:
    """Normaliza a entrada `message` para uma lista de mensagens.

    Aceita string única, lista ou tupla. Retorna sempre uma lista.
    """
    if isinstance(message, (list, tuple)):
        return list(message)
    return [message]


def _normalize_extras(extra, count: int) -> list:
    """Normaliza o parâmetro `extra` para uma lista com comprimento `count`.

    - Se `extra` for None, retorna lista de None.
    - Se for dict, replica para cada mensagem.
    - Se for lista/tupla, ajusta o tamanho (preenche com None se necessário).
    - Caso contrário, replica o valor para cada item.
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


def write_log(
    name: str,
    level: str,
    message: str | list[str],
    extra: dict | list[dict] | None = None,
    human_enable: bool = True,
    json_enable: bool = True,
    safe_log_enable: bool = False,
) -> None:
    """Write one or more entries to .log and .jsonl files."""
    filename = _resolve_filename(name, safe_log_enable)

    messages = _normalize_messages(message)
    extras_list = _normalize_extras(extra, len(messages))

    lp = get_log_paths()
    plain_path = lp.log_dir / f"{filename}.log"
    jsonl_path = lp.json_dir / f"{filename}.jsonl"

    for idx, msg in enumerate(messages):
        ts = datetime.now(timezone.utc).isoformat()

        human_msg = normalize_message_for_human(msg)
        if human_enable:
            human_line = build_human_line(ts, level, human_msg, extras_list[idx])
            write_text(plain_path, human_line)

        if json_enable:
            per_extra = extras_list[idx] if extras_list is not None else None
            json_obj = build_json_entry(ts, level, msg, per_extra)
            write_json(jsonl_path, json_obj)
