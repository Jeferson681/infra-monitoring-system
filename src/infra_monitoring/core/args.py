"""Argument parsing utilities for the monitoring CLI.

Provides a configured ArgumentParser and helpers to parse and validate
runtime options such as collection interval, number of cycles and
logging configuration. Environment variable overrides are applied only
when the corresponding CLI argument is not provided.
"""

# Auto-adjust sys.path for direct execution or when run with -m
import sys
from pathlib import Path

if __name__ == "__main__" or (hasattr(sys, "_getframe") and sys._getframe(1).f_globals.get("__name__") == "__main__"):
    src_path = Path(__file__).resolve().parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

import argparse
from typing import Sequence


# Main function in the module; create and return a configured ArgumentParser
def configure_argparser() -> argparse.ArgumentParser:
    """Create and return an ArgumentParser configured for the monitoring CLI."""
    parser = argparse.ArgumentParser(
        prog="monitoring",
        description="Monitoring program: collections, logging and automated treatments",
    )

    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=3.0,
        help="Interval in seconds between collections (float). Minimum recommended: 0.1",
    )
    parser.add_argument(
        "-c",
        "--cycles",
        type=int,
        default=1,
        help="Number of cycles to run (0 = infinite) or total time in minutes when --cycle-mode=time.",
    )
    parser.add_argument(
        "--cycle-mode",
        choices=["cycles", "time"],
        default="cycles",
        help="Execution mode: 'cycles' for number of cycles, 'time' for total minutes.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv)",
    )
    parser.add_argument(
        "--log-root",
        dest="log_root",
        type=str,
        default=None,
        help="Root path for logs (overrides MONITORING_LOG_ROOT)",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        type=str,
        default=None,
        help="Logging level (DEBUG/INFO/WARNING/ERROR). If absent, determined by -v",
    )

    return parser


# Assists src.main; created to parse argv and validate arguments
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse argv and return a validated Namespace for program use."""
    import os

    parser = configure_argparser()
    ns = parser.parse_args(argv)
    # Mapping of arguments to environment variables
    env_map = {
        "interval": "MONITORING_INTERVAL_SEC",
        "cycles": "MONITORING_CYCLES",
        "cycle_mode": "MONITORING_CYCLE_MODE",
        "verbose": "MONITORING_VERBOSE",
        "log_root": "MONITORING_LOG_ROOT",
        "log_level": "MONITORING_LOG_LEVEL",
    }
    import logging

    # Apply overrides via environment variables ONLY when the argument
    # was not provided on the command line (CLI takes precedence).
    for arg, env_var in env_map.items():
        env_val = os.getenv(env_var)
        if env_val is None:
            continue
        # if the user provided the argument via CLI, do not overwrite
        try:
            default_val = parser.get_default(arg)
        except Exception:
            default_val = None
        current_val = getattr(ns, arg, None)
        if current_val is not None and current_val != default_val:
            # CLI-provided value takes precedence
            continue
        try:
            if arg == "interval":
                setattr(ns, arg, float(env_val))
            elif arg in ("cycles", "verbose"):
                setattr(ns, arg, int(env_val))
            else:
                setattr(ns, arg, env_val)
        except Exception as exc:
            logging.getLogger(__name__).warning(f"{env_var} invalid ('{env_val}'): {exc}. Using CLI/default value.")
    # If in time mode, allow override via a specific env var
    if getattr(ns, "cycle_mode", "cycles") == "time":
        env_time = os.getenv("MONITORING_CYCLE_TIME_MIN")
        if env_time is not None:
            try:
                ns.cycles = int(env_time)
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    f"MONITORING_CYCLE_TIME_MIN invalid ('{env_time}'): {exc}. Using CLI/default value."
                )
    validate_args(ns)
    return ns


# Helper for parse_args; created to ensure correct and safe values
def validate_args(args: argparse.Namespace) -> None:
    """Validate and normalize arguments for the monitoring program."""
    if getattr(args, "interval", 1.0) is None:
        args.interval = 1.0
    try:
        args.interval = float(args.interval)
    except (TypeError, ValueError) as exc:
        raise ValueError("interval must be a number") from exc
    if args.interval < 0.0:
        raise ValueError("interval must be >= 0.0")

    try:
        args.cycles = int(args.cycles)
    except (TypeError, ValueError) as exc:
        raise ValueError("cycles/time must be an integer >= 0") from exc
    if args.cycles < 0:
        raise ValueError("cycles/time must be >= 0")


# Assists src.main; created to extract logging configuration from arguments
def get_log_config(args: argparse.Namespace) -> dict:
    """Return a dict with logging configuration ('level' and 'root') for monitoring."""
    if getattr(args, "log_level", None):
        level = str(args.log_level).upper()
    else:
        v = getattr(args, "verbose", 0) or 0
        if v >= 1:
            level = "INFO"
        else:
            level = "DEBUG"

    return {"level": level, "root": getattr(args, "log_root", None)}
