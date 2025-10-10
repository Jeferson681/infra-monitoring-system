# vulture: ignore
"""Helpers de baixo nível para o subsistema de logging.

Fornece compressão, verificação de idade de ficheiros,
movimentações atômicas e escrita durável em disco.
"""

from pathlib import Path
from datetime import datetime, timezone, date
import logging
import gzip
import shutil
import time
import os
import json as _json
import re

try:
    import portalocker  # type: ignore
except ImportError:  # dependência opcional
    portalocker = None

logger = logging.getLogger(__name__)

ROTATING_SUFFIX = ".rotating"

# Durabilidade controlada via settings ou variável de ambiente
try:
    from config.settings import LOGS_DURABLE_WRITES  # type: ignore

    DURABLE_WRITES = bool(LOGS_DURABLE_WRITES)
except (ImportError, AttributeError):
    DURABLE_WRITES = os.environ.get("LOGS_DURABLE_WRITES", "1").lower() in ("1", "true", "yes", "on")


# -----------------------
# Escrita segura
# -----------------------
def write_text(path: Path, text: str) -> None:
    """Anexa texto a `path`, com lock e fsync se configurado."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            locked = False
            try:
                if portalocker is not None:
                    try:
                        portalocker.lock(fh, portalocker.LOCK_EX)
                        locked = True
                    except Exception as exc:
                        logger.debug("write_text: portalocker.lock falhou em %s: %s", path, exc)

                fh.write(text)
                fh.flush()

                if DURABLE_WRITES:
                    try:
                        os.fsync(fh.fileno())
                    except Exception as exc:
                        logger.debug("write_text: fsync falhou em %s: %s", path, exc)
            finally:
                if locked and portalocker and hasattr(portalocker, "unlock"):
                    try:
                        portalocker.unlock(fh)
                    except Exception as exc:
                        logger.debug("write_text: portalocker.unlock falhou em %s: %s", path, exc)
    except OSError as exc:
        logger.warning("write_text: falhou em %s: %s", path, exc)


def write_json(path: Path, obj: dict) -> None:
    """Serializa `obj` em JSONL e anexa a `path`."""
    try:
        line = _json.dumps(obj, ensure_ascii=False) + "\n"
    except (TypeError, ValueError) as exc:
        try:
            line = _json.dumps(obj, ensure_ascii=False, default=str) + "\n"
            logger.warning("write_json: fallback default=str usado em %s: %s", path, exc)
        except Exception as exc2:
            logger.warning("write_json: falhou em %s: %s; %s", path, exc, exc2)
            return
    write_text(path, line)


# -----------------------
# Normalização e formatação
# -----------------------
def sanitize_log_name(raw_name: str, fallback: str = "debug_log") -> str:
    """Sanitiza nome base de ficheiro de log."""
    rn = Path(raw_name or fallback).name.lstrip(".")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", rn)
    if not name:
        name = fallback
    if len(name) > 200:
        name = name[:200]
    return name


def normalize_message_for_human(msg, max_len: int | None = 10000) -> str:
    """Normaliza mensagem para linha legível por humanos."""
    try:
        s = "" if msg is None else str(msg)
    except (TypeError, ValueError):
        s = "<unrepr>"
    s = s.replace("\n", " ").replace("\r", " ")
    return s[:max_len] if max_len and len(s) > max_len else s


def build_json_entry(ts: str, level: str, msg, extra: dict | None = None) -> dict:
    """Constrói dicionário serializável para JSONL."""
    entry = {"ts": ts, "level": level, "msg": msg}
    if extra and isinstance(extra, dict):
        for k, v in extra.items():
            entry[k if k not in entry else f"extra_{k}"] = v
    elif extra:
        entry["meta"] = extra
    return entry


def build_human_line(ts: str, level: str, msg_str: str, extras: dict | None = None) -> str:
    """Compõe linha legível por humanos.

    Formato resultante:
      <ts> [LEVEL] [extras...]
      <msg_str>

    Onde <msg_str> pode conter múltiplas linhas (preservadas). Esta mudança
    garante que o cabeçalho com data e nível fique numa linha separada e que a
    primeira métrica (por exemplo, CPU) comece na linha seguinte.
    """
    extras_part = ""
    if extras and isinstance(extras, dict):
        kvs = []
        for k, v in extras.items():
            sval = str(v) if not isinstance(v, (list, dict)) else repr(v)
            sval = sval.replace("\n", " ").replace("\r", " ")
            kvs.append(f"{k}={sval}")
        if kvs:
            extras_part = " " + " ".join(kvs)

    # Ensure msg_str is a string and preserve internal newlines.
    try:
        body = "" if msg_str is None else str(msg_str)
    except Exception:
        body = "<unrepr>"

    # Trim trailing whitespace/newlines but keep internal line breaks.
    body = body.rstrip("\r\n")

    header = f"{ts} [{level}]{extras_part}\n"
    # Append an extra blank line to separate entries visually.
    return header + body + "\n\n"


def format_date_for_log(dt=None) -> str:
    """Retorna data no formato YYYY-MM-DD (segura para nomes)."""
    try:
        if dt is None:
            return date.today().isoformat()
        if isinstance(dt, date):
            return dt.isoformat()
        return dt.date().isoformat()
    except (AttributeError, TypeError):
        return datetime.now(timezone.utc).date().isoformat()


# -----------------------
# Verificação de idade
# -----------------------
def is_older_than(p: Path, seconds: int) -> bool:
    """Return True se o ficheiro tiver mtime mais antigo que `seconds`."""
    try:
        st = p.stat()
    except OSError as exc:
        logger.warning("is_older_than: falha ao acessar %s: %s", p, exc)
        return False
    now_ts = datetime.now(timezone.utc).timestamp()
    return st.st_mtime <= (now_ts - int(seconds))


def archive_file_is_old(p: Path, now_ts: float, retention_days: int) -> bool:
    """Return True se o ficheiro em archive for mais antigo que `retention_days`."""
    try:
        st = p.stat()
    except OSError as exc:
        logger.warning("archive_file_is_old: falha ao acessar %s: %s", p, exc)
        return False
    cutoff = now_ts - retention_days * 86400
    return st.st_mtime < cutoff


# -----------------------
# Rotação / Compressão
# -----------------------
def _attempt_rename(s: Path, d: Path) -> bool:
    try:
        s.rename(d)
        return True
    except OSError as exc:
        logger.debug("atomic_move_to_archive: rename failed: %s", exc)
        return False


def _attempt_replace(s: Path, d: Path) -> bool:
    try:
        os.replace(s, d)
        return True
    except OSError as exc:
        logger.debug("atomic_move_to_archive: os.replace failed: %s", exc)
        return False


def _copy_replace_fallback(s: Path, d: Path) -> bool:
    tmp = d.with_suffix(d.suffix + ".tmp")
    try:
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, tmp)
        os.replace(tmp, d)
        try:
            s.unlink(missing_ok=True)
        except OSError:
            pass
        return True
    except OSError as exc:
        logger.debug("atomic_move_to_archive: copy fallback failed: %s", exc, exc_info=True)
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        return False


def atomic_move_to_archive(src: Path, dst_rotating: Path) -> bool:
    """Move `src` para `dst_rotating` de forma atômica, com backoff e fallbacks."""
    attempts = 5
    base_delay = 0.05
    for i in range(attempts):
        if _attempt_rename(src, dst_rotating):
            return True
        if _attempt_replace(src, dst_rotating):
            return True
        if _copy_replace_fallback(src, dst_rotating):
            return True
        if i + 1 < attempts:
            time.sleep(base_delay * (2**i))
    try:
        if dst_rotating.exists() and not src.exists():
            dst_rotating.unlink()
    except Exception as exc3:
        logger.warning("atomic_move_to_archive: cleanup failed on %s: %s", dst_rotating, exc3)
    return False


def compress_file(src: Path, dst_gz: Path) -> bool:
    """Comprime `src` em gzip `dst_gz`. Usa escrita temporária + replace atômico."""
    dst_gz.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst_gz.with_suffix(dst_gz.suffix + ".tmp")
    try:
        with src.open("rb") as rf, gzip.open(tmp, "wb") as gf:
            shutil.copyfileobj(rf, gf)
        os.replace(str(tmp), str(dst_gz))
        return True
    except OSError as exc:
        logger.warning("compress_file: falha %s -> %s: %s", src, dst_gz, exc)
        tmp.unlink(missing_ok=True)
        return False


def try_rotate_file(p: Path, archive_dir: Path, gz_suffix: str, day_secs: int, week_secs: int) -> None:
    """Move e comprime ficheiro de log para archive, respeitando safe-retention."""
    threshold = week_secs if "_safe" in p.name else day_secs
    if not is_older_than(p, threshold):
        return
    rotating = archive_dir / (p.name + ROTATING_SUFFIX)
    if not atomic_move_to_archive(p, rotating):
        return
    gz_path = archive_dir / f"{p.stem}{gz_suffix}"
    if compress_file(rotating, gz_path):
        rotating.unlink(missing_ok=True)


def try_compress_rotating(rotating: Path, archive_dir: Path, day_secs: int, week_secs: int) -> None:
    """Tenta comprimir um ficheiro `.rotating` já movido para archive."""
    threshold = week_secs if "_safe" in rotating.name else day_secs
    if not is_older_than(rotating, threshold):
        return
    gz_path = archive_dir / (rotating.stem + ".gz")
    if compress_file(rotating, gz_path):
        rotating.unlink(missing_ok=True)


# -----------------------
# Limpeza temporária
# -----------------------
def all_children_old(d: Path, max_age: int) -> bool:
    """Retorna True se todos os filhos de `d` tiverem idade maior que `max_age`."""
    try:
        return all(is_older_than(c, max_age) for c in d.iterdir())
    except OSError:
        return False


def process_temp_item(item: Path, max_age: int) -> None:
    """Remove ficheiros ou diretórios temporários antigos."""
    try:
        if item.is_file() and is_older_than(item, max_age):
            item.unlink(missing_ok=True)
            logger.info("Removido %s", item)
        elif item.is_dir() and all_children_old(item, max_age) and is_older_than(item, max_age):
            shutil.rmtree(item, ignore_errors=True)
            logger.info("Removido diretório %s", item)
    except OSError as exc:
        logger.warning("Falha processando %s: %s", item, exc)


# -----------------------
# Diretórios / permissões
# -----------------------
def ensure_dir_writable(p: Path) -> bool:
    """Garante, em melhor esforço, que `p` existe e é gravável."""
    try:
        p.mkdir(parents=True, exist_ok=True)
        test = p / f".touch-{os.getpid()}"
        try:
            with open(test, "w") as f:
                f.write("ok")
        finally:
            test.unlink(missing_ok=True)
        return True
    except OSError as exc:
        logger.warning("ensure_dir_writable: failed for %s: %s", p, exc)
    return False
