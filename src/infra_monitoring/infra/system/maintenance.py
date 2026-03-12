"""Maintenance helpers: rotation, compression, safe removal and hourly aggregation.

Centralized periodic routines extracted from the orchestration layer to
enable isolated testing and reuse. Exposes functions to read configured
intervals and run scheduled maintenance tasks.
"""

from __future__ import annotations

import logging

from infra_monitoring.infra.system.logs import (
    compress_old_logs,
    get_log_paths,
    rotate_logs,
    safe_remove,
)
from infra_monitoring.services.monitoring.averages import (
    aggregate_last_seconds,
    write_average_log,
)


def _read_maintenance_intervals() -> tuple[int, int, int, int]:
    """Read maintenance intervals from environment with sensible defaults.

    Returns (rotate_interval, compress_interval, safe_remove_interval, hourly_interval)
    in seconds. Invalid environment values are handled using safe defaults.
    """
    import os

    try:
        rotate_interval = int(
            os.getenv("MONITORING_ROTATE_INTERVAL_SEC", str(24 * 3600))
        )
    except (TypeError, ValueError):
        rotate_interval = 24 * 3600
    try:
        compress_interval = int(
            os.getenv("MONITORING_COMPRESS_INTERVAL_SEC", str(24 * 3600))
        )
    except (TypeError, ValueError):
        compress_interval = 24 * 3600
    try:
        safe_remove_interval = int(
            os.getenv("MONITORING_SAFE_REMOVE_INTERVAL_SEC", str(24 * 3600 * 7))
        )
    except (TypeError, ValueError):
        safe_remove_interval = 24 * 3600 * 7
    try:
        hourly_interval = int(os.getenv("MONITORING_HOURLY_INTERVAL_SEC", str(3600)))
    except (TypeError, ValueError):
        hourly_interval = 3600
    return rotate_interval, compress_interval, safe_remove_interval, hourly_interval


def _maintenance_rotate(now: float, last_rotate: float, rotate_interval: int) -> float:
    """Run log rotation when the configured interval is reached.

    Returns the new `last_rotate` timestamp (used for scheduling).
    """
    if now - last_rotate >= rotate_interval:
        try:
            rotate_logs()
        except OSError as exc:
            logging.getLogger(__name__).warning("Failed to rotate logs: %s", exc)
        except Exception as exc:
            logging.getLogger(__name__).debug(
                "rotate_logs: unexpected error: %s", exc, exc_info=True
            )
        return now
    return last_rotate


def _maintenance_compress(
    now: float, last_compress: float, compress_interval: int
) -> float:
    """Run log compression when the configured interval is reached.

    Returns the new `last_compress` timestamp.
    """
    if now - last_compress >= compress_interval:
        try:
            compress_old_logs()
        except OSError as exc:
            logging.getLogger(__name__).warning("Failed to compress logs: %s", exc)
        except Exception as exc:
            logging.getLogger(__name__).debug(
                "compress_old_logs: unexpected error: %s", exc, exc_info=True
            )
        return now
    return last_compress


def _maintenance_safe_remove(
    now: float, last_safe_remove: float, safe_remove_interval: int
) -> float:
    """Run safe removal of old files when the configured interval is reached.

    Returns the new `last_safe_remove` timestamp.
    """
    if now - last_safe_remove >= safe_remove_interval:
        try:
            safe_remove()
        except OSError as exc:
            logging.getLogger(__name__).warning("Failed to remove old files: %s", exc)
        except Exception as exc:
            logging.getLogger(__name__).debug(
                "safe_remove: unexpected error: %s", exc, exc_info=True
            )
        return now
    return last_safe_remove


def _maintenance_hourly(now: float, last_hourly: float, hourly_interval: int) -> float:
    """Schedule and run the hourly aggregation task.

    Attempts to aggregate the last `hourly_interval` seconds of logs and
    persist them. Returns the new `last_hourly` timestamp on success, else
    returns the previous value.
    """
    try:
        if now - last_hourly >= hourly_interval:
            try:
                lp = get_log_paths()
                root = lp.root
                agg = aggregate_last_seconds(logs_root=root, seconds=hourly_interval)

                if agg:
                    try:
                        # Maintenance scheduling already enforces the hourly interval;
                        # avoid suppressing the write again via the logging subsystem's
                        # per-log hourly window mechanism.
                        write_average_log(
                            agg, hourly=False, hourly_window_seconds=hourly_interval
                        )
                    except Exception as exc:
                        logging.getLogger(__name__).debug(
                            "write_average_log failed: %s", exc, exc_info=True
                        )
            except Exception as exc:
                logging.getLogger(__name__).debug(
                    "Hourly aggregation failed: %s", exc, exc_info=True
                )
            return now
    except Exception as exc:
        logging.getLogger(__name__).debug(
            "Error scheduling hourly aggregation: %s", exc, exc_info=True
        )
    return last_hourly


def _run_maintenance(
    now: float,
    last_rotate: float,
    last_compress: float,
    last_safe_remove: float,
    last_hourly: float,
    intervals: tuple[int, int, int, int],
) -> tuple[float, float, float, float]:
    """Run periodic maintenance tasks.

    Accepts reference timestamps and intervals and returns potentially
    updated timestamps after executing maintenance tasks.
    """
    rotate_interval, compress_interval, safe_remove_interval, hourly_interval = (
        intervals
    )

    last_rotate = _maintenance_rotate(now, last_rotate, rotate_interval)
    last_compress = _maintenance_compress(now, last_compress, compress_interval)
    last_safe_remove = _maintenance_safe_remove(
        now, last_safe_remove, safe_remove_interval
    )
    last_hourly = _maintenance_hourly(now, last_hourly, hourly_interval)

    return last_rotate, last_compress, last_safe_remove, last_hourly
