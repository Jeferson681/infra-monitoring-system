"""Implementation of automated treatments and system maintenance actions.

Simple corrective actions (memory, network, disk, logs) and helpers used by
the treatment orchestration. Functions are designed to be best-effort and to
log failures rather than raising in the main monitoring loop.
"""

import datetime
import logging
import os
import shutil
import socket
import string
import sys
import tempfile
from pathlib import Path

from .helpers import get_network_limit, reap_children_nonblocking, record_network_usage
from .log_helpers import process_temp_item

logger = logging.getLogger(__name__)

# Configuration constants
NETWORK_EXCESS_THRESHOLD_SECONDS = 300  # 5 minutes
NETWORK_TREATMENT_COOLDOWN_SECONDS = 3 * 24 * 3600  # 3 days


## ...existing code...

_excess_since: float | None = None


def update_network_usage_learning(bytes_sent: int, bytes_recv: int) -> bool:
    """Update network usage learning and check if consumption exceeds learned limit."""
    record_network_usage(bytes_sent, bytes_recv)
    limit = get_network_limit()
    total = bytes_sent + bytes_recv
    allowed_hour = os.environ.get("NETWORK_TREATMENT_ALLOWED_HOUR")
    current_hour = datetime.datetime.now().hour
    # Persist the excess period for 5 minutes before acting
    now = datetime.datetime.now().timestamp()
    global _excess_since
    if total > limit:
        if _excess_since is None:
            _excess_since = now
        excess_duration = now - _excess_since
    else:
        _excess_since = None
        excess_duration = 0

    # Configurable hourly window
    if allowed_hour is None:
        return False
    try:
        allowed_hour_int = int(allowed_hour)
    except Exception:
        allowed_hour_int = None
    if allowed_hour_int is None or current_hour != allowed_hour_int:
        return False

    # If the excess persists for more than 5 minutes and the hourly lock is active, trigger treatment
    if total > limit and excess_duration >= NETWORK_EXCESS_THRESHOLD_SECONDS:
        try:
            from . import treatments

            restart_func = getattr(treatments, "restart_interface", None)
            if restart_func is not None:
                restart_func()
        except Exception as exc:
            logger.warning(
                "update_network_usage_learning: restart_interface failed: %s",
                exc,
                exc_info=True,
            )
        return True
    return False


# vulture: ignore
"""Simple automated treatments (memory, network, disk, logs)."""


# vulture: ignore
def cleanup_temp_files(days: int = 7) -> None:
    """Remove old temporary files from the system temp directory.

    Walks the system temp directory and removes items older than `days`.
    Designed to be used as a helper maintenance action.
    """
    tmpdir = Path(tempfile.gettempdir())
    max_age = days * 86400
    if not tmpdir.exists():
        logger.debug("cleanup_temp_files: tempdir %s does not exist", tmpdir)
        return

    try:
        for item in sorted(tmpdir.iterdir()):
            process_temp_item(item, max_age)
    except OSError as exc:
        # Debug log; do not raise when scanning tempdir
        logger.debug(
            "cleanup_temp_files: scanning %s failed: %s", tmpdir, exc, exc_info=True
        )


# vulture: ignore
def check_disk_usage(threshold_pct: int = 90) -> list[str]:
    """Check disk usage and log/return issues above the threshold.

    Returns a list of messages describing volumes whose usage exceeds
    `threshold_pct`.
    """
    roots = _iter_roots()
    issues: list[str] = []
    for r in roots:
        try:
            exists = r.exists()
        except OSError:
            # volume inaccessible or no recognized filesystem
            continue
        if not exists:
            continue
        try:
            pct = _disk_usage_pct(r)
            if pct >= threshold_pct:
                issues.append(f"{r}: {pct}% used")
        except Exception as exc:
            issues.append(f"{r}: error {exc}")
    for i in issues:
        logger.warning("Disk usage issue: %s", i)
    return issues


def _disk_usage_pct(r: Path) -> int:
    """Return the used percentage of the filesystem at `r` as an integer.

    Propagates exceptions from `shutil.disk_usage` so the caller can handle them.
    """
    usage = shutil.disk_usage(r)
    return int((usage.used / usage.total * 100) if usage.total else 0)


def _iter_roots() -> list[Path]:
    """Return the list of roots to check for disk usage.

    On Windows this returns existing drive letters; on POSIX returns ['/'].
    """
    if os.name == "nt":
        # Return only existing drive letters
        roots: list[Path] = []
        for d in string.ascii_uppercase:
            p = Path(f"{d}:/")
            if p.exists():
                roots.append(p)
        return roots or [Path("/")]
    return [Path("/")]


# vulture: ignore


def trim_process_working_set_windows(pid: int) -> bool:
    """Try to reduce a process working set on Windows using EmptyWorkingSet.

    Returns True on success, False on non-Windows platforms or on failure.
    The type: ignore is required because WinDLL only exists on Windows.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes

        PROCESS_SET_QUOTA = 0x0100
        PROCESS_QUERY_INFORMATION = 0x0400

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        psapi = ctypes.WinDLL("psapi", use_last_error=True)  # type: ignore[attr-defined]

        h = kernel32.OpenProcess(
            PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION, False, pid
        )
        if not h:
            return False
        try:
            res = psapi.EmptyWorkingSet(h)
            return bool(res)
        finally:
            kernel32.CloseHandle(h)
    except Exception as exc:
        logger.debug("trim_process_working_set_windows failed: %s", exc, exc_info=True)
        return False


def trim_process_working_set_posix(pid: int) -> bool:
    """Best-effort: attempt to reduce a process working set on POSIX systems.

    Notes:
    - Linux/glibc provides ``malloc_trim(0)`` which can release unused heap
      memory back to the kernel, but it only affects the calling process.
    - Trimming another process's working set is not generally possible from
      user-space in a portable, safe way; therefore this function only
      attempts to act when ``pid`` refers to the current process.
    - The operation is best-effort and failures are logged and return False.

    """
    if os.name != "posix":
        return False
    try:
        # Only attempt to act on the current process; acting on another PID is not portable.
        if int(pid) != os.getpid():
            return False

        import ctypes

        # Try common libc names first, then the process namespace.
        for libname in ("libc.so.6", None):
            try:
                libc = ctypes.CDLL(libname) if libname else ctypes.CDLL(None)
            except Exception:
                libc = None
            if not libc:
                continue
            malloc_trim = getattr(libc, "malloc_trim", None)
            if malloc_trim is None:
                continue
            try:
                # call: int malloc_trim(size_t pad)
                res = malloc_trim(0)
                return bool(res)
            except Exception as exc:
                logger.debug(
                    "trim_process_working_set_posix: malloc_trim failed: %s",
                    exc,
                    exc_info=True,
                )
                return False
        return False
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(
            "trim_process_working_set_posix unexpected error: %s", exc, exc_info=True
        )
        return False


def reap_zombie_processes() -> int:
    """Reap zombie processes on POSIX platforms.

    Returns the number of processes collected.
    """
    if os.name != "posix":
        return 0
    try:
        reaped = reap_children_nonblocking()
    except Exception as exc:
        logger.debug("cleanup_processes: reap failed: %s", exc, exc_info=True)
        return 0
    count = len(reaped)
    if count:
        logger.info("Collected %d zombie processes", count)
    return count


# vulture: ignore
def reapply_network_config() -> None:
    """Attempt to restore network connectivity by running platform commands.

    Uses `_platform_candidates` to obtain platform-appropriate commands and
    `_online_check` to stop once connectivity is restored.
    """
    if _online_check():
        return

    candidates = _platform_candidates(sys.platform)
    if not candidates:
        logger.debug(
            "reapply_network_config: no candidate commands for platform %s",
            sys.platform,
        )
        logger.warning("Could not restore network connectivity")
        return

    for cmd in candidates:
        if shutil.which(cmd[0]) is None:
            logger.debug(
                "reapply_network_config: command not found, skipping %s", cmd[0]
            )
            continue

        try:
            import subprocess  # nosec B404 - used with vetted list args and no shell

            # subprocess.run used with list args and without shell=True; commands
            # are validated by `shutil.which` and come from internal candidates.
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)  # nosec B603
        except (subprocess.SubprocessError, OSError) as exc:
            logger.error(
                "reapply_network_config: %s failed: %s", cmd, exc, exc_info=True
            )
            continue

        logger.debug(
            "reapply_network_config: %s => %s", cmd, getattr(proc, "returncode", None)
        )
        if _online_check():
            logger.info("Network connectivity restored after %s", cmd)
            return

    logger.warning("Could not restore network connectivity")


def _platform_candidates(p: str) -> list:
    """Return a list of candidate commands to restore networking for the platform."""
    p = (p or "").lower()
    if p.startswith("linux"):
        return [["resolvectl", "flush-caches"], ["nmcli", "networking", "on"]]
    if p == "win32":
        return [["ipconfig", "/flushdns"]]
    if p == "darwin":
        return [["dscacheutil", "-flushcache"]]
    return []


def _online_check(timeout: float = 2.0) -> bool:
    """Check external connectivity by attempting a TCP connection with a timeout.

    Returns True on success, False otherwise.
    """
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=timeout):
            return True
    except OSError:
        return False


# Silence Vulture: these functions are invoked dynamically by
# `monitoring.handlers` via getattr(action_name) at runtime and are
# therefore incorrectly reported as unused by static analyzers.
_VULTURE_KEEP = [
    cleanup_temp_files,
    check_disk_usage,
    trim_process_working_set_windows,
    trim_process_working_set_posix,
    reap_zombie_processes,
    reapply_network_config,
]
