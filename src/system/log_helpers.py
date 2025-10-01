"""Helpers de baixo nível para o subsistema de logging.

Fornece compressão, verificação de idade de ficheiros, movimentações atômicas
e escritas duráveis.
"""

from pathlib import Path
from datetime import datetime, timezone
import logging
import gzip
import shutil
import time
import os
import json as _json
import re

try:
    import portalocker  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    portalocker = None

logger = logging.getLogger(__name__)

# Control durable fsync behavior via settings or environment variable.
try:
    from config.settings import LOGS_DURABLE_WRITES  # type: ignore

    DURABLE_WRITES = bool(LOGS_DURABLE_WRITES)
except Exception:
    DURABLE_WRITES = os.environ.get("LOGS_DURABLE_WRITES", "1").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

ROTATING_SUFFIX = ".rotating"


def is_older_than(p: Path, seconds: int) -> bool:
    """Retorna True quando ``p`` tem mtime mais antigo do que ``seconds``.

    Regista um warning e retorna False em caso de erro no stat.
    """
    try:
        st = p.stat()
    except Exception as exc:
        logging.getLogger(__name__).warning("is_older_than: failed to stat %s: %s", p, exc)
        return False
    now_ts = datetime.now(timezone.utc).timestamp()
    return st.st_mtime <= (now_ts - int(seconds))


def archive_file_is_old(p: Path, now_ts: float, retention_days: int) -> bool:
    """Retorna True quando o ficheiro de archive ``p`` é mais antigo que o período ``retention_days``.

    Centraliza a lógica de cálculo de datas para o subsistema de logs.
    """
    try:
        st = p.stat()
    except Exception as exc:
        logging.getLogger(__name__).warning("archive_file_is_old: failed to stat %s: %s", p, exc)
        return False
    cutoff = now_ts - int(retention_days) * 24 * 60 * 60
    return st.st_mtime < cutoff


def compress_file(src: Path, dst_gz: Path) -> bool:
    """Comprime ``src`` -> ``dst_gz`` usando gzip. Retorna True em sucesso.

    Escreve primeiro num ficheiro temporário e faz replace atômico para evitar
    arquivos parciais ou corrompidos.
    """
    tmp = dst_gz.with_suffix(dst_gz.suffix + ".tmp")
    try:
        # write to a temp file first
        with src.open("rb") as rf, gzip.open(tmp, "wb") as gf:
            shutil.copyfileobj(rf, gf)
        # atomic replace
        tmp.replace(dst_gz)
        return True
    except Exception as exc:
        logger.warning(
            "compress_file: failed to compress %s -> %s: %s",
            src,
            dst_gz,
            exc,
        )
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception as exc2:
            logger.warning(
                "compress_file: failed to cleanup temp %s: %s",
                tmp,
                exc2,
            )
        return False


def format_date_for_log(dt=None) -> str:
    """Retorna uma string de data adequada para nomes de ficheiro: YYYY-MM-DD.

    Aceita datetime.date, datetime.datetime ou None (por defeito hoje). Sempre
    devolve uma string no formato ISO (sem parte de tempo) segura para nomes.
    """
    try:
        from datetime import date as _date

        if dt is None:
            return _date.today().isoformat()
        if isinstance(dt, _date):
            return dt.isoformat()
        # assume datetime-like
        return dt.date().isoformat()
    except Exception:
        # last-resort fallback
        return datetime.now(timezone.utc).date().isoformat()


def atomic_move_to_archive(src: Path, dst_rotating: Path) -> bool:
    """Tenta mover atomicamente ``src`` para ``dst_rotating`` com retries.

    Implementação de baixo nível para evitar ficheiros parcialmente movidos
    por colisões de I/O. Retorna True em sucesso.
    """
    logger = logging.getLogger(__name__)

    attempts = 5
    base_delay = 0.05

    for i in range(attempts):
        try:
            src.rename(dst_rotating)
            return True
        except Exception as exc:
            # fallback to os.replace
            try:
                os.replace(src, dst_rotating)
                return True
            except Exception as exc2:
                logger.debug(
                    "atomic_move_to_archive: attempt %d failed: %s; %s",
                    i + 1,
                    exc,
                    exc2,
                )
                if i + 1 < attempts:
                    time.sleep(base_delay * (2**i))
                else:
                    break

    logger.warning(
        "atomic_move_to_archive: failed to move %s after %d attempts",
        src,
        attempts,
    )
    try:
        if dst_rotating.exists() and not src.exists():
            dst_rotating.unlink()
    except Exception as exc2:
        logger.warning(
            "atomic_move_to_archive: cleanup partial rotating failed for %s: %s",
            dst_rotating,
            exc2,
        )
    return False


def write_text(path: Path, text: str) -> None:
    """Anexa texto a ``path`` garantindo lock quando possível.

    Usa `portalocker` se disponível; realiza fsync conforme configuração
    para garantir durabilidade.
    """
    logger = logging.getLogger(__name__)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if portalocker is not None:
            with path.open("a", encoding="utf-8") as fh:
                portalocker.lock(fh, portalocker.LOCK_EX)
                fh.write(text)
                fh.flush()
                if DURABLE_WRITES:
                    try:
                        # ensure data is on disk to avoid loss on crash
                        os.fsync(fh.fileno())
                    except Exception as exc:
                        logger.debug(
                            "write_text: fsync failed for %s: %s",
                            path,
                            exc,
                        )
                portalocker.unlock(fh)
        else:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(text)
                fh.flush()
                if DURABLE_WRITES:
                    try:
                        os.fsync(fh.fileno())
                    except Exception as exc:
                        logger.debug(
                            "write_text: fsync failed for %s: %s",
                            path,
                            exc,
                        )
    except Exception as exc:
        logger.warning(
            "write_text: Failed to write text log %s: %s",
            path,
            exc,
        )


def write_json(path: Path, obj: dict) -> None:
    """Serializa ``obj`` como uma linha JSONL e anexa ao ficheiro ``path``.

    Tenta serializar com fallback `default=str` para objetos não serializáveis.
    """
    logger = logging.getLogger(__name__)
    try:
        line = _json.dumps(obj, ensure_ascii=False) + "\n"
    except Exception as exc:
        # first fallback: attempt to serialize using default=str to handle
        # non-serializable objects (common and safe fallback)
        try:
            line = _json.dumps(obj, ensure_ascii=False, default=str) + "\n"
            logger.warning(
                "write_json: used fallback default=str for %s: %s",
                path,
                exc,
            )
        except Exception as exc2:
            logger.warning(
                "write_json: Failed to serialize JSON for %s (primary and fallback): %s; %s",
                path,
                exc,
                exc2,
            )
            return
    write_text(path, line)


def sanitize_log_name(raw_name: str, fallback: str = "debug_log") -> str:
    """Sanitiza um nome base para ficheiros de log.

    Remove componentes de caminho, substitui caracteres inválidos e limita
    o comprimento para evitar nomes problemáticos.
    """
    rn = Path(raw_name or fallback).name.lstrip(".")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", rn)
    if not name:
        name = fallback
    if len(name) > 200:
        name = name[:200]
    return name


def normalize_message_for_human(msg, max_len: int | None = 10000) -> str:
    """Normaliza uma mensagem para linhas de log humanas.

    Converte para str(), colapsa novas linhas e opcionalmente trunca.
    """
    try:
        s = "" if msg is None else str(msg)
    except Exception:
        s = "<unrepr>"
    # collapse newlines to spaces
    s = s.replace("\n", " ").replace("\r", " ")
    if max_len is not None and len(s) > max_len:
        return s[:max_len]
    return s


def build_json_entry(ts: str, level: str, msg, extra: dict | None = None) -> dict:
    """Constrói um dicionário serializável para gravar em JSONL.

    Insere campos básicos e mescla `extra` quando for um dicionário.
    """
    entry: dict = {"ts": ts, "level": level, "msg": msg}
    if extra:
        if isinstance(extra, dict):
            for k, v in extra.items():
                if k in entry:
                    entry[f"extra_{k}"] = v
                else:
                    entry[k] = v
        else:
            entry["meta"] = extra
    return entry


def build_human_line(ts: str, level: str, msg_str: str, extras: dict | None = None) -> str:
    r"""Compõe uma única linha de log legível por humanos.

    Formato: "<ts> [LEVEL] mensagem <extras>\n".
    """
    extras_part = ""
    if extras and isinstance(extras, dict):
        kvs = []
        for k, v in extras.items():
            try:
                sval = str(v)
            except Exception:
                sval = "<unrepr>"
            sval = sval.replace("\n", " ").replace("\r", " ")
            kvs.append(f"{k}={sval}")
        if kvs:
            extras_part = " " + " ".join(kvs)
    return f"{ts} [{level}] {msg_str}{extras_part}\n"


def try_rotate_file(
    p: Path,
    archive_dir: Path,
    gz_suffix: str,
    day_secs: int,
    week_secs: int,
) -> None:
    """Tenta mover e comprimir um único arquivo de log para o diretório de archive.

    Usa os helpers de baixo nível (atomic_move_to_archive, compress_file) e
    preserva arquivos marcados com "_safe" por um período maior.
    """
    threshold = week_secs if "_safe" in p.name else day_secs
    if not is_older_than(p, threshold):
        return

    base = p.stem
    rotating = archive_dir / (p.name + ROTATING_SUFFIX)
    if not atomic_move_to_archive(p, rotating):
        return

    gz_path = archive_dir / f"{base}{gz_suffix}"
    if compress_file(rotating, gz_path):
        try:
            rotating.unlink()
        except Exception as exc:
            logger.warning(
                "try_rotate_file: failed to unlink %s: %s",
                rotating,
                exc,
            )


def try_compress_rotating(
    rotating: Path,
    archive_dir: Path,
    day_secs: int,
    week_secs: int,
) -> None:
    """Tenta comprimir um arquivo '.rotating' no diretório de archive."""
    try:
        name = rotating.name
        if name.endswith(f".jsonl{ROTATING_SUFFIX}"):
            base = name.removesuffix(f".jsonl{ROTATING_SUFFIX}")
            gz_suffix = ".jsonl.gz"
        elif name.endswith(f".log{ROTATING_SUFFIX}"):
            base = name.removesuffix(f".log{ROTATING_SUFFIX}")
            gz_suffix = ".log.gz"
        else:
            p = Path(name)
            suffixes = p.suffixes
            if len(suffixes) >= 2:
                original = suffixes[-2]
                base = name.removesuffix(original + ROTATING_SUFFIX)
                gz_suffix = original + ".gz"
            else:
                base = name.removesuffix(ROTATING_SUFFIX)
                gz_suffix = ".gz"

        threshold = week_secs if "_safe" in name else day_secs
        if not is_older_than(rotating, threshold):
            return

        gz_path = archive_dir / f"{base}{gz_suffix}"
        if compress_file(rotating, gz_path):
            try:
                rotating.unlink()
            except Exception as exc2:
                logger.warning(
                    "try_compress_rotating: failed to unlink %s: %s",
                    rotating,
                    exc2,
                )
    except Exception as exc:
        logger.warning(
            "try_compress_rotating: failed for %s: %s",
            rotating,
            exc,
        )
