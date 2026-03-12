"""General system helper utilities.

Small, lightweight helpers used across subsystems (host/port validation,
reading simple .env files, candidate disk paths, etc.). Implementations are
best-effort and minimize external dependencies to remain import-friendly in
tests and CLI contexts.
"""

import datetime
import json
import logging
import os
import socket
import time
from pathlib import Path


def get_project_root() -> Path:
    """Return the project root directory.

    This repository is structured as `<root>/src/...`; this helper returns
    `<root>` by walking up from this module's location.
    """
    # helpers.py lives at: <root>/src/infra_monitoring/infra/system/helpers.py
    # Walk up four levels to reach the repository root ("<root>").
    return Path(__file__).resolve().parents[4]


def update_network_usage_learning(bytes_sent: int, bytes_recv: int) -> bool:
    """Update network usage learning and check if the learned limit is exceeded."""
    # Delegate to the canonical implementation in `infra_monitoring.infra.system.treatments`.
    # Keep this wrapper for API compatibility and to avoid duplicating logic.
    try:
        from .treatments import update_network_usage_learning as _impl

        return _impl(bytes_sent, bytes_recv)
    except Exception:
        # If delegation fails for any reason (import/runtime),
        # conservatively return False.
        return False


NETWORK_LEARNING_FILE = Path(".cache/network_usage_learning.json")


def ensure_cache_dir_exists():
    """Ensure the .cache directory exists."""
    NETWORK_LEARNING_FILE.parent.mkdir(parents=True, exist_ok=True)


NETWORK_LEARNING_WEEKS = 4
NETWORK_DEFAULT_LIMIT = 20 * 1024**3  # 20GB
NETWORK_MARGIN = 0.2  # 20%


def record_network_usage(bytes_sent: int, bytes_recv: int) -> None:
    """Persist network usage for daily learning of automatic limit."""
    today = datetime.date.today().isoformat()
    data = {}
    if NETWORK_LEARNING_FILE.exists():
        try:
            with NETWORK_LEARNING_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[today] = {"bytes_sent": bytes_sent, "bytes_recv": bytes_recv}
    try:
        NETWORK_LEARNING_FILE.parent.mkdir(parents=True, exist_ok=True)
        with NETWORK_LEARNING_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as exc:
        logging.getLogger(__name__).error(
            "Failed to save network usage data: %s", exc, exc_info=True
        )


# Cache for get_network_limit() to avoid frequent file reads
_network_limit_cache: dict[str, float | int] = {
    "value": NETWORK_DEFAULT_LIMIT,
    "ts": 0.0,
}


def get_network_limit() -> int:
    """Return the current limit for bytes_sent/bytes_recv, learned over 4 weeks.

    Uses a 60-second cache to avoid frequent file reads.
    """
    global _network_limit_cache
    now = time.monotonic()

    # If the cache is still valid (< 60 seconds), return cached value
    if now - _network_limit_cache["ts"] < 60.0:
        return int(_network_limit_cache["value"])
    if not NETWORK_LEARNING_FILE.exists():
        return NETWORK_DEFAULT_LIMIT
    try:
        with NETWORK_LEARNING_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return NETWORK_DEFAULT_LIMIT
    # Group data by ISO year/week
    weeks: dict[tuple[int, int], list[int]] = {}
    for date_str, usage in data.items():
        dt = datetime.date.fromisoformat(date_str)
        year_week = dt.isocalendar()[:2]
        if year_week not in weeks:
            weeks[year_week] = []
        weeks[year_week].append(usage["bytes_sent"] + usage["bytes_recv"])
    if len(weeks) < NETWORK_LEARNING_WEEKS:
        return NETWORK_DEFAULT_LIMIT
    # Compute weekly average
    all_values = [v for week in weeks.values() for v in week]
    avg = sum(all_values) / max(1, len(all_values))
    limit = int(avg * (1 + NETWORK_MARGIN))

    # Update cache
    _network_limit_cache["value"] = limit
    _network_limit_cache["ts"] = now

    return limit


# vulture: ignore

logger = logging.getLogger(__name__)


def reap_children_nonblocking() -> list[tuple[int, int]]:
    """Reap terminated child processes in a non-blocking manner (POSIX).

    Returns a list of (pid, status) tuples for reaped processes. On
    non-POSIX platforms returns an empty list.
    """
    reaped: list[tuple[int, int]] = []
    if os.name == "posix":
        try:
            # Some static analyzers/mypy complain about direct access to
            # `os.WNOHANG` on platforms where the constant may not exist.
            # Use getattr with a fallback to preserve POSIX behavior and
            # avoid typing errors on other platforms.
            flags = getattr(os, "WNOHANG", 1)
            while True:
                pid, status = os.waitpid(-1, flags)
                if pid == 0:
                    break
                reaped.append((pid, status))
        except ChildProcessError:
            pass  # no child processes
        except OSError:
            pass  # platform or permission issue
    return reaped


def validate_host_port(host: str, port: int) -> bool:
    """Validate a host:port pair for use in network connections.

    Returns True when `host` is a valid IPv4 address and the port is in the
    range (1..65535).
    """
    try:
        socket.inet_aton(host)
        return 0 < port < 65536
    except (OSError, ValueError):
        return False


def _disk_candidate_paths() -> list[object]:
    r"""Return candidate paths to check for disk usage.

    The generated list attempts to use the system anchor (e.g. "C:\\" on
    Windows), then the POSIX root and finally the literal '/' as a fallback.
    """
    # Path is already imported at module level

    candidates: list[object] = []
    try:
        anchor = Path().anchor
        if anchor:
            candidates.append(Path(anchor))
    except Exception as exc:
        # Best-effort fallback for Path.anchor access; record debug info
        import logging as _logging

        _logging.getLogger(__name__).debug(
            "Path.anchor access failed, falling back", exc_info=exc
        )
    candidates.append(Path("/"))
    candidates.append("/")
    return candidates


def read_env_file(path: Path | str) -> dict:
    """Read a simple `.env` file and return a key->value dictionary.

    Rules:
    - Empty lines and lines starting with '#' are ignored.
    - The first '=' separates key/value; surrounding single or double
      quotes are removed from the value.
    - If the file does not exist, returns an empty dict.
    """
    # Path is already imported at module level

    result: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return result
    try:
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                # strip surrounding whitespace and quotes
                val = val.strip().strip('"').strip("'")
                # remove inline comments after the value (e.g. "7  # default")
                if "#" in val:
                    val = val.split("#", 1)[0].rstrip()
                result[key] = val
    except OSError:
        # Best-effort: return empty mapping on read errors
        return {}
    return result


def read_jsonl(path: Path | str, use_lock: bool = False) -> list[dict]:
    """Read a .jsonl file and return a list of dicts. Uses portalocker if requested."""
    p = Path(path)
    entries = []
    portalocker = None
    if use_lock:
        try:
            import portalocker as _portalocker

            portalocker = _portalocker
        except ImportError:
            pass

    def _parse_jsonl_lines(fh):
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception as exc:
                logging.warning(f"Invalid JSON line ignored: {exc}")

    try:
        if use_lock and portalocker:
            with portalocker.Lock(str(p), "r", encoding="utf-8") as fh:
                _parse_jsonl_lines(fh)
        else:
            with p.open("r", encoding="utf-8") as fh:
                _parse_jsonl_lines(fh)
    except OSError:
        return []
    return entries


def merge_env_items(env_path: Path, process_env: dict) -> dict:
    """Merge items from a `.env` file into the process environment.

    The `process_env` mapping (usually ``os.environ``) takes precedence over
    keys from the file. This function has no side effects on inputs.
    """
    file_items = read_env_file(env_path)
    # Make a copy to avoid mutating inputs
    out = dict(file_items)
    out.update(dict(process_env))
    return out
