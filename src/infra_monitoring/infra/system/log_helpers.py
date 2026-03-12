"""Low-level helpers for the logging subsystem.

Provides compression, file-age checks, atomic moves and durable disk
writing helpers used by the higher-level logging subsystem. Implementations
favor robustness and best-effort behavior for I/O operations.
"""

import gzip
import json as _json
import logging
import os
import re
import shutil
import time
from datetime import UTC, date, datetime
from pathlib import Path

try:
    import portalocker  # type: ignore
except ImportError:
    # optional dependency
    portalocker = None

logger = logging.getLogger(__name__)

ROTATING_SUFFIX = ".rotating"

# Durability controlled via settings or environment variable
try:
    from config.settings import LOGS_DURABLE_WRITES  # type: ignore

    DURABLE_WRITES = bool(LOGS_DURABLE_WRITES)
except (ImportError, AttributeError):
    DURABLE_WRITES = os.environ.get("LOGS_DURABLE_WRITES", "1").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


# -----------------------
# Safe writing
# -----------------------
def write_text(path: Path, text: str) -> bool:
    """Append text to `path` safely, using a lock and fsync when available.

    This function attempts to create the parent directory and applies an
    exclusive lock when the `portalocker` library is available. On failure
    it logs a warning and proceeds in a best-effort mode.
    """
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
                        logger.debug(
                            "write_text: portalocker.lock failed on %s: %s", path, exc
                        )

                fh.write(text)
                fh.flush()

                if DURABLE_WRITES:
                    try:
                        os.fsync(fh.fileno())
                    except Exception as exc:
                        logger.debug("write_text: fsync failed on %s: %s", path, exc)
            finally:
                if locked and portalocker and hasattr(portalocker, "unlock"):
                    try:
                        portalocker.unlock(fh)
                    except Exception as exc:
                        logger.debug(
                            "write_text: portalocker.unlock failed on %s: %s", path, exc
                        )
        return True
    except PermissionError as exc:
        # Permission issues are non-fatal for the main loop; warn for
        # visibility without marking the service as failed.
        logger.warning(
            "write_text: permission denied writing to %s: %s", path, exc, exc_info=True
        )
        return False
    except OSError as exc:
        logger.error("write_text: failed on %s: %s", path, exc, exc_info=True)
        return False


def write_json(path: Path, obj: dict) -> bool:
    """Serialize an object as JSONL and append to `path`.

    If objects are not serializable by default, uses `default=str` as a
    fallback and emits a warning.
    """
    try:
        line = _json.dumps(obj, ensure_ascii=False) + "\n"
    except (TypeError, ValueError) as exc:
        try:
            line = _json.dumps(obj, ensure_ascii=False, default=str) + "\n"
            # Emit a WARNING for fallback serialization; recoverable but
            # indicates non-strictly-serializable types.
            logger.warning(
                "write_json: fallback default=str used on %s: %s",
                path,
                exc,
                exc_info=True,
            )
        except Exception as exc2:
            logger.error(
                "write_json: failed on %s: %s; %s", path, exc, exc2, exc_info=True
            )
            return False
    return write_text(path, line)


# -----------------------
# Normalization and formatting
# -----------------------
def sanitize_log_name(raw_name: str, fallback: str = "debug_log") -> str:
    """Sanitize a base log filename for safe filesystem use.

    Removes potentially dangerous characters and limits length. Returns a
    safe name suitable for use as a filename.
    """
    rn = Path(raw_name or fallback).name.lstrip(".")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", rn)
    if not name:
        name = fallback
    if len(name) > 200:
        name = name[:200]
    return name


def normalize_message_for_human(msg, max_len: int | None = 10000) -> str:
    """Normalize a message for human presentation by removing newlines.

    Truncates the message to `max_len` when set.
    """
    try:
        s = "" if msg is None else str(msg)
    except (TypeError, ValueError):
        s = "<unrepr>"
    s = s.replace("\n", " ").replace("\r", " ")
    return s[:max_len] if max_len and len(s) > max_len else s


def build_json_entry(ts: str, level: str, msg, extra: dict | None = None) -> dict:
    """Build a dictionary ready to be serialized as JSONL.

    Inserts `ts`, `level`, `msg` and merges `extra` when provided.
    """
    entry = {"ts": ts, "level": level, "msg": msg}
    if extra and isinstance(extra, dict):
        for k, v in extra.items():
            entry[k if k not in entry else f"extra_{k}"] = v
    elif extra:
        entry["meta"] = extra
    return entry


def build_human_line(
    ts: str, level: str, msg_str: str, extras: dict | None = None
) -> str:
    r"""Compose a human-readable log line.

    For compatibility with existing consumers the legacy format is a single
    line with timestamp, level, extras and a flattened message. A newer
    multiline format (header + body) can be enabled via the
    environment variable `MONITORING_HUMAN_MULTILINE=1`.

    Legacy (default):
        <ts> [LEVEL] [extras...] <msg_str>\n
    Multiline (optional):
        <ts> [LEVEL] [extras...]\n
        <msg_str>\n\n
    """
    # decide whether to use the multiline format
    use_multiline = _should_use_multiline(msg_str)

    extras_part = _format_extras_for_human(extras)

    # Ensure msg_str is a string
    try:
        body = "" if msg_str is None else str(msg_str)
    except Exception:
        body = "<unrepr>"

    if use_multiline:
        # Multiline: preserve internal newlines, strip trailing newlines and keep a blank separator
        body = body.rstrip("\r\n")
        header = f"{ts} [{level}]{extras_part}\n"
        return header + body + "\n\n"
    else:
        # Legacy format: flatten newline characters into spaces
        single = body.replace("\n", " ").replace("\r", " ").strip()
        return f"{ts} [{level}]{extras_part} {single}\n"


def _format_extras_for_human(extras: dict | None) -> str:
    """Format the `extras` dict into a single string for human logs.

    Extracted from `build_human_line` to reduce complexity.
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
    return extras_part


def _should_use_multiline(msg_str: object) -> bool:
    """Decide whether to use the multiline format for human messages.

    Prefer multiline when the environment variable indicates or when the
    message contains internal newline characters.
    """
    try:
        use_multiline_env = os.environ.get("MONITORING_HUMAN_MULTILINE", "0") in (
            "1",
            "true",
            "yes",
        )
    except Exception:
        use_multiline_env = False

    if use_multiline_env:
        return True
    try:
        if isinstance(msg_str, str) and ("\n" in msg_str or "\r" in msg_str):
            return True
    except Exception:
        return False
    return False


def format_date_for_log(dt=None) -> str:
    """Return a YYYY-MM-DD date suitable for filenames."""
    try:
        if dt is None:
            return date.today().isoformat()
        # datetime is a subclass of date; prefer to return only the date
        # portion when a full datetime is provided.
        if isinstance(dt, datetime):
            return dt.date().isoformat()
        if isinstance(dt, date):
            return dt.isoformat()
        return datetime.now(UTC).date().isoformat()
    except (AttributeError, TypeError):
        return datetime.now(UTC).date().isoformat()


# -----------------------
# Age checks
# -----------------------
def is_older_than(p: Path, seconds: int) -> bool:
    """Return True if the file's mtime is older than `seconds`."""
    try:
        st = p.stat()
    except OSError as exc:
        logger.error("is_older_than: failed accessing %s: %s", p, exc, exc_info=True)
        return False
    now_ts = datetime.now(UTC).timestamp()
    return st.st_mtime <= (now_ts - int(seconds))


def archive_file_is_old(p: Path, now_ts: float, retention_days: int) -> bool:
    """Return True if the archive file is older than `retention_days`."""
    try:
        st = p.stat()
    except OSError as exc:
        logger.error(
            "archive_file_is_old: failed accessing %s: %s", p, exc, exc_info=True
        )
        return False
    cutoff = now_ts - retention_days * 86400
    return st.st_mtime < cutoff


# -----------------------
# Rotation / Compression
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
        logger.debug(
            "atomic_move_to_archive: copy fallback failed: %s", exc, exc_info=True
        )
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        return False


def atomic_move_to_archive(src: Path, dst_rotating: Path) -> bool:
    """Move `src` to `dst_rotating` atomically, with backoff and fallbacks."""
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
        logger.error(
            "atomic_move_to_archive: cleanup failed on %s: %s",
            dst_rotating,
            exc3,
            exc_info=True,
        )
    return False


def compress_file(src: Path, dst_gz: Path) -> bool:
    """Compress `src` into gzip `dst_gz`. Uses temporary write + atomic replace."""
    dst_gz.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst_gz.with_suffix(dst_gz.suffix + ".tmp")
    try:
        with src.open("rb") as rf, gzip.open(tmp, "wb") as gf:
            shutil.copyfileobj(rf, gf)
        os.replace(str(tmp), str(dst_gz))
        return True
    except OSError as exc:
        logger.error(
            "compress_file: failed %s -> %s: %s", src, dst_gz, exc, exc_info=True
        )
        tmp.unlink(missing_ok=True)
        return False


def try_rotate_file(
    p: Path, archive_dir: Path, gz_suffix: str, day_secs: int, week_secs: int
) -> None:
    """Move and compress a log file into archive, respecting safe-retention."""
    threshold = week_secs if "_safe" in p.name else day_secs
    if not is_older_than(p, threshold):
        return
    rotating = archive_dir / (p.name + ROTATING_SUFFIX)
    if not atomic_move_to_archive(p, rotating):
        return
    gz_path = archive_dir / f"{p.stem}{gz_suffix}"
    if compress_file(rotating, gz_path):
        rotating.unlink(missing_ok=True)


def try_compress_rotating(
    rotating: Path, archive_dir: Path, day_secs: int, week_secs: int
) -> None:
    """Try to compress a `.rotating` file that was moved to archive."""
    threshold = week_secs if "_safe" in rotating.name else day_secs
    if not is_older_than(rotating, threshold):
        return
    gz_path = archive_dir / (rotating.stem + ".gz")
    if compress_file(rotating, gz_path):
        rotating.unlink(missing_ok=True)


# -----------------------
# Temporary cleanup
# -----------------------
def all_children_old(d: Path, max_age: int) -> bool:
    """Return True if all children of `d` have ages greater than `max_age`."""
    try:
        return all(is_older_than(c, max_age) for c in d.iterdir())
    except OSError:
        return False


def process_temp_item(item: Path, max_age: int) -> None:
    """Remove old temporary files or directories."""
    try:
        if item.is_file() and is_older_than(item, max_age):
            item.unlink(missing_ok=True)
            logger.info("Removed %s", item)
        elif (
            item.is_dir()
            and all_children_old(item, max_age)
            and is_older_than(item, max_age)
        ):
            shutil.rmtree(item, ignore_errors=True)
            logger.info("Removed directory %s", item)
    except OSError as exc:
        logger.error("Failed processing %s: %s", item, exc, exc_info=True)


# -----------------------
# Directories / permissions
# -----------------------
def ensure_dir_writable(p: Path) -> bool:
    """Ensure, in a best-effort manner, that `p` exists and is writable."""
    try:
        p.mkdir(parents=True, exist_ok=True)
        test = p / f".touch-{os.getpid()}"
        try:
            # open in append mode to minimize permission surprises
            with open(test, "a", encoding="utf-8") as f:
                f.write("ok")
                f.flush()
        except PermissionError as exc:
            # Permission issues are non-fatal for the main loop; warn and
            # return False so callers can handle accordingly.
            logger.warning(
                "ensure_dir_writable: permission denied writing to %s: %s",
                p,
                exc,
                exc_info=True,
            )
            return False
        except OSError as exc:
            logger.error(
                "ensure_dir_writable: write test failed for %s: %s",
                p,
                exc,
                exc_info=True,
            )
            return False
        finally:
            try:
                if test.exists():
                    test.unlink()
            except Exception as exc:
                # Ignore cleanup failures; best-effort operation only.
                import logging as _logging

                _logging.getLogger(__name__).debug(
                    "cleanup failed during ensure_dir_writable", exc_info=exc
                )
        return True
    except PermissionError as exc:
        logger.warning(
            "ensure_dir_writable: permission denied creating %s: %s",
            p,
            exc,
            exc_info=True,
        )
        return False
    except OSError as exc:
        logger.error("ensure_dir_writable: failed for %s: %s", p, exc, exc_info=True)
        return False
