"""Logging subsystem: rotation, compression and persistence.

High-level helpers for writing human-readable logs and JSONL ingestion
records, rotating and compressing archived files and preparing log
directories. Designed to be robust and tolerant to I/O failures.
"""

import os

# Keep internal comments minimal; errno handling is not required here
import logging

import time
from dataclasses import dataclass
from datetime import datetime, timezone

from pathlib import Path
from typing import Optional

from .helpers import get_project_root

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


@dataclass(frozen=True)
class LogPaths:
    """Group paths used by the logging subsystem.

    Contains the root, log, json, archive and debug directories used by
    write/rotation/cleanup helpers.
    """

    root: Path
    log_dir: Path
    json_dir: Path
    archive_dir: Path
    debug_dir: Path

    def __iter__(self):
        """Yield a tuple with the main paths."""
        return iter((self.root, self.log_dir, self.json_dir, self.archive_dir))


def get_log_paths(root: str | Path | None = None) -> LogPaths:
    """Resolve the log root and ensure writable directories exist.

    Returns a `LogPaths` object with directories prepared for writing and
    reading by the logging and archive subsystems.
    """
    try:
        # Prefer caller-provided root, then environment variable, then module-level LOG_ROOT
        env_root = os.getenv("MONITORING_LOG_ROOT")
        if root:
            candidate = root
        elif env_root is not None:
            candidate = env_root
        else:
            candidate = LOG_ROOT
        log_root = Path(candidate)
    except Exception as exc:
        logger.debug("get_log_paths: failed to resolve root: %s", exc, exc_info=True)
        log_root = get_project_root() / "logs"

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
    return LogPaths(log_root, log_dir, json_dir, archive_dir, debug_dir)


# Generate the base filename for logs; consumed by write_log
def _resolve_filename(name: str, safe_log_enable: bool) -> str:
    """Generate a log filename base including optional safe suffix and date.

    Normalizes the name and appends a `_safe` suffix when requested.
    """
    default = DEBUG_LOG_FILENAME
    base = sanitize_log_name(name or default, default)
    if safe_log_enable:
        base = f"{base}_safe"
    date_str = format_date_for_log(None)
    return f"{base}-{date_str}"


# Normalize message inputs; used by write_log
def _normalize_messages(message) -> list:
    """Accept a single string, list or tuple and return a list.

    Ensures downstream logic that iterates messages always works with a list.
    """
    if isinstance(message, (list, tuple)):
        return list(message)
    return [message]


# Normalize the extra field to a list of the required length; used by write_log
def _normalize_extras(extra, count: int) -> list:
    """Normalize extras to a fixed-length list.

    Accepts a dict (replicated), list/tuple or None; guarantees length `count`.
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


# Write messages to .log and .jsonl; feeds analysis and ingestion pipelines
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
    """Write messages to a plain-text log and/or a JSONL file.

    Contract and behavior:
        - `human_enable`: when True, write a human-readable line to ``.log``;
            by default this is suppressed for 'hourly' files unless the window
            (`hourly_window_seconds`) allows it.
        - `json_enable`: when True, write a structured object to ``.jsonl`` for
            downstream ingestion.
        - `safe_log_enable`: when True, append a `_safe` suffix to the filename
            and preserve the original human multi-line text when applicable.

    Robustness notes:
        - Writes use atomic helpers (`write_text`, `write_json`) that return
            ``True``/``False``; this function ignores write failures (does not
            raise) but logs warnings when a write fails.
        - The function has no return value (side-effect only). Callers should
            rely on logs for diagnosing I/O failures.

    Parameters (summary):
        - name: logical name of the log stream (used to name files).
        - level: textual level (e.g. 'info', 'error').
        - message: string or list of strings to write.
        - extra: optional metadata (dict or list of dicts) associated with lines.
        - human_enable/json_enable/safe_log_enable: flags described above.
        - log: when False avoid human writes except when hourly is active.
        - hourly/hourly_window_seconds: control aggregated windowed writes.
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


# Helper for write_log: decide whether human write is allowed by hourly window
def _hourly_allows_write(
    name: str, hourly: bool, hourly_window_seconds: int, project_root: Optional[Path] = None
) -> bool:
    """Check whether the 'hourly' window allows a write.

    Returns True when not in hourly mode or when the time since the last
    human write exceeds `hourly_window_seconds`. The optional `project_root`
    parameter allows specifying the base directory for tests.
    """
    if not hourly:
        return True
    try:
        key = sanitize_log_name(name, name)
        if project_root is None:
            project_root = get_project_root()
        cache_dir = project_root / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
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
        logger.debug("_hourly_allows_write: error checking hourly: %s", exc, exc_info=True)
        return True


# Helper for write_log: write human line to .log and update hourly timestamp
def _perform_human_write(
    plain_path: Path,
    name: str,
    level: str,
    human_msg: str,
    extra: dict | None,
    hourly: bool,
    hourly_window_seconds: int,
    log: bool,
) -> None:
    """Perform the human-readable file write, respecting flags and hourly window.

    Details:
        - Build a readable text line with timestamp and level via
          `build_human_line` and delegate to `write_text` (which performs an
          atomic write).
        - If `write_text` fails a WARNING is logged; the function avoids
          raising to not interrupt the main loop.
        - When `hourly` is active and the write succeeds, update a control
          file in ``.cache`` containing the timestamp of the last human write
          to control future aggregated writes.
    """
    if not log and not hourly:
        logger.debug("human write suppressed (log=False and hourly=False)")
        return

    if _hourly_allows_write(name, hourly, hourly_window_seconds):
        human_line = build_human_line(format_date_for_log(None), level, human_msg, extra)
        ok = write_text(plain_path, human_line)
        if not ok:
            logger.warning("_perform_human_write: failed to write human log %s", plain_path)
        if hourly and ok:
            try:
                cache_dir = get_project_root() / ".cache"
                cache_dir.mkdir(parents=True, exist_ok=True)
                ts_file = cache_dir / (f".last_human_{sanitize_log_name(name, name)}.ts")
                with open(ts_file, "w", encoding="utf-8") as f:
                    f.write(str(int(time.time())))
            except Exception as exc:
                logger.debug("_perform_human_write: failed to write hourly ts: %s", exc, exc_info=True)
    else:
        # More explicit message to aid diagnosis when a human write is
        # suppressed by the 'hourly' mechanism. Including the log name and
        # window length helps identify aggregated callers (e.g. average_log).
        try:
            logger.debug(
                "Human write suppressed for '%s': within hourly window of %s seconds; recent write",
                name,
                hourly_window_seconds,
            )
        except Exception:
            # simple fallback if formatting the message fails
            logger.debug("human write ignored by hourly window")


# Helper for write_log: build and write a JSON object to JSONL for ingestion
def _perform_json_write(jsonl_path: Path, ts: str, level: str, msg, extra: dict | None) -> None:
    """Build the JSON object and delegate to `write_json`.

    Keeps a format compatible with metrics/ingestion consumers.
    """
    # Avoid including human-oriented summaries in the canonical JSON feed.
    # Keep only machine-readable keys and metrics.
    safe_extra = None
    if isinstance(extra, dict):
        safe_extra = {k: v for k, v in extra.items() if k not in ("summary_short", "summary_long")}
    json_obj = build_json_entry(ts, level, msg, safe_extra)
    ok = write_json(jsonl_path, json_obj)
    if ok is False:
        logger.warning("_perform_json_write: failed to write jsonl %s", jsonl_path)


# Return the path to today's debug file; used by debug logging
def get_debug_file_path() -> Path:
    """Return the path to today's debug file.

    Names the file with the current date inside the debug directory.
    """
    date_str = format_date_for_log(None)
    filename = f"debug_log-{date_str}.txt"
    return get_log_paths().debug_dir / filename


# Loop helper: check and recreate log directories if needed
def ensure_log_dirs_exist(root: str | Path | None = None) -> None:
    """Ensure the log directories exist and recreate them if missing.

    Performs cheap checks (Path.exists()) and only escalates to full
    creation by calling the initializer when a path is missing. Designed to
    be called frequently from the loop without significant overhead.
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
                # this creates the directories by calling get_log_paths (which uses
                # ensure_dir_writable internally)
                get_log_paths(root)
            except Exception as exc:
                logger.debug("ensure_log_dirs_exist: failed to recreate %s: %s", p, exc, exc_info=True)
            break


def rotate_logs(day_secs: int | None = None, week_secs: int | None = None) -> None:
    """Rotate logs to archive."""
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
    """Compress old rotating files in the archive."""
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
    """Remove old files from the archive according to retention rules."""
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
                logger.error("safe_remove: failed to remove %s: %s", p, exc, exc_info=True)
