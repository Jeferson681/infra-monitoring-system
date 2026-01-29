"""Program entrypoint for the monitoring application.

This module initializes the application: it parses CLI arguments, configures
logging, installs debug handlers and starts the main monitoring loop. Runtime
logic is kept in the ``core`` package to simplify testing and reuse.
"""

from .core.args import parse_args, get_log_config
import logging as _logging
import sys
from .system.logs import get_debug_file_path
from .core.core import run_loop
import os

# Ensure the averages subsystem has its control timestamp file present.
# This prepares the hourly cache/state used by aggregations.
from .monitoring.averages import ensure_default_last_ts

import json as _json


def main(argv: list[str] | None = None) -> None:
    """Initialize the application and start the main monitoring loop.

    Args:
        argv: List of arguments (used by tests). When ``None``, arguments are
            parsed from the current process command line.

    Returns:
        None

    """
    # Load defaults from a .env file when present. Do not override existing
    # process environment variables; this is a best-effort convenience for
    # local development and tests.
    try:
        from src.system.helpers import read_env_file, get_project_root

        env_path = get_project_root() / ".env"
        env_items = read_env_file(env_path)
        for k, v in env_items.items():
            if os.getenv(k) is None:
                os.environ[k] = v
    except Exception:
        _logging.getLogger(__name__).debug("failed to load .env via helper", exc_info=True)

    # Support test harnesses that pass an empty argv list by applying
    # known defaults rather than reading the process args.
    if argv is None:
        args = parse_args(None)
    else:
        if isinstance(argv, list) and len(argv) == 0:
            argv = ["-i", "1", "-c", "0"]
        args = parse_args(argv)
    log_conf = get_log_config(args)

    level = getattr(_logging, log_conf.get("level", "WARNING"), _logging.WARNING)
    _logging.basicConfig(level=level, format="%(asctime)s %(levelname)s: %(message)s")

    try:
        _setup_debug_file_handler()
    except Exception as exc:
        _logging.getLogger(__name__).debug("failed to configure debug file handler: %s", exc, exc_info=True)

    # Ensure control cache file exists before starting the loop. Failures are
    # non-fatal and logged at debug level to avoid breaking startup.
    try:
        ensure_default_last_ts()
    except Exception:
        _logging.getLogger(__name__).debug("failed to ensure control file at startup", exc_info=True)
    # Optionally start Prometheus exporter if enabled via env
    try:
        from .exporter.prometheus import start_exporter

        if os.getenv("MONITORING_EXPORTER_ENABLE", "0") in ("1", "true", "yes"):
            try:
                start_exporter()
            except Exception:
                _logging.getLogger(__name__).debug("failed to start Prometheus exporter", exc_info=True)
    except Exception:
        _logging.getLogger(__name__).debug("exporter not available", exc_info=True)

    # Start optional fallback HTTP metrics server in a separate thread when
    # explicitly enabled. This is kept separate to avoid bind conflicts with
    # the Prometheus exporter when both are present.
    try:
        # Only start the fallback HTTP server when explicitly enabled to avoid
        # starting two competing metric servers (prometheus_client vs fallback).
        if os.getenv("MONITORING_HTTP_ENABLE", "0") in ("1", "true", "yes"):
            # If exporter already started a metrics server, skip to avoid bind conflicts.
            try:
                from src.exporter import prometheus as _prom

                if getattr(_prom, "_server_started", False):
                    _logging.getLogger(__name__).info(
                        "Metrics server already started by exporter; skipping fallback HTTP server"
                    )
                else:
                    from src.exporter.main_http import run_http_server
                    import threading

                    port = int(os.getenv("MONITORING_HTTP_PORT", "8000"))
                    # Allow explicit override from environment so orchestrators
                    # (e.g., docker-compose) can request a different bind
                    # address. Default to localhost to avoid accidental exposure
                    # when the program is run directly by a user.
                    addr = os.getenv("MONITORING_HTTP_ADDR")
                    if not addr:
                        addr = "127.0.0.1"
                    http_thread = threading.Thread(
                        target=run_http_server, kwargs={"addr": addr, "port": port}, daemon=True
                    )
                    http_thread.start()
            except Exception:
                # If we cannot import the exporter module, proceed to start the HTTP server.
                from src.exporter.main_http import run_http_server
                import threading

                port = int(os.getenv("MONITORING_HTTP_PORT", "8000"))
                addr = os.getenv("MONITORING_HTTP_ADDR", "127.0.0.1")
                http_thread = threading.Thread(target=run_http_server, kwargs={"addr": addr, "port": port}, daemon=True)
                http_thread.start()

            # Optionally start a promtail/loki heartbeat worker if enabled via
            # MONITORING_PROMTAIL_ENABLE. This emits periodic heartbeats for
            # remote log collectors and is run in a background thread.
            if os.getenv("MONITORING_PROMTAIL_ENABLE", "0") in ("1", "true", "yes"):
                try:
                    from src.exporter.main_http import run_promtail_worker

                    promtail_thread = threading.Thread(target=run_promtail_worker, daemon=True)
                    promtail_thread.start()
                except Exception:
                    _logging.getLogger(__name__).debug("failed to start promtail worker", exc_info=True)
    except Exception as exc:
        _logging.getLogger(__name__).warning("Failed to start metrics HTTP server: %s", exc, exc_info=True)

    run_loop(interval=args.interval, cycles=args.cycles, verbose_level=getattr(args, "verbose", 0) or 0)


def _setup_debug_file_handler() -> None:
    """Install file handlers for debug output and a global exception hook.

    Adds two handlers to the root logger: a human-readable text handler and a
    JSONL handler (one JSON object per event) intended for downstream
    ingestion. Installation is best-effort: handler write failures are
    suppressed to avoid logging causing application crashes. A ``sys.excepthook``
    is installed to route uncaught exceptions to the root logger.

    Notes:
        - Duplicate handlers for the same filenames are avoided.
        - Handler ``emit`` methods are wrapped to suppress handler-internal
            exceptions so logging failures do not propagate to application code.

    """
    debug_path = get_debug_file_path()

    # Human-readable file handler (plain-text) for operators and local debugging
    fh = _logging.FileHandler(str(debug_path), encoding="utf-8")
    fh.setLevel(_logging.INFO)
    fmt = _logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh.setFormatter(fmt)

    jpath = debug_path.with_suffix(".jsonl")
    jfh = _logging.FileHandler(str(jpath), encoding="utf-8")
    jfh.setLevel(_logging.INFO)
    jfh.setFormatter(_get_json_formatter())

    root = _logging.getLogger()
    if not _has_existing_file_handler(root, fh, jfh):
        _wrap_emit_safe(fh)
        _wrap_emit_safe(jfh)
        root.addHandler(fh)
        root.addHandler(jfh)

    def _exc_hook(exc_type, exc_value, exc_tb):
        try:
            root.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        except Exception:
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _exc_hook

    # Helper utilities extracted to reduce complexity of the main flow


def _get_json_formatter():
    """Return a logging.Formatter subclass that formats records as compact JSON.

    The returned formatter produces a single-line JSON object with keys:
    ``ts``, ``level``, ``name`` and ``msg``. If exception information is
    present, an ``exc`` field with the formatted traceback is included.
    """

    class _JSONFormatter(_logging.Formatter):
        """Formatter that serializes LogRecord objects to JSONL-compatible strings."""

        def format(self, record):
            try:
                ts = self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                ts = ""
            obj = {
                "ts": ts,
                "level": record.levelname,
                "name": record.name,
                "msg": record.getMessage(),
            }
            if record.exc_info:
                try:
                    import traceback as _tb

                    obj["exc"] = "".join(_tb.format_exception(*record.exc_info))
                except Exception:
                    _logging.getLogger(__name__).warning("Failed to format exc_info for JSON", exc_info=True)
            return _json.dumps(obj, ensure_ascii=False)

    return _JSONFormatter()


def _has_existing_file_handler(root, fh, jfh):
    """Return True if a FileHandler for either `fh` or `jfh` is already attached.

    This prevents adding duplicate file handlers that would write to the same
    filenames. The function is best-effort and returns False on unexpected
    errors to avoid blocking handler installation.
    """
    try:
        bases = (getattr(fh, "baseFilename", None), getattr(jfh, "baseFilename", None))
        for h in root.handlers:
            if isinstance(h, _logging.FileHandler):
                if getattr(h, "baseFilename", None) in bases:
                    return True
    except Exception:
        _logging.getLogger(__name__).exception("error inspecting handler")
    return False


def _wrap_emit_safe(handler):
    """Wrap the handler.emit method to suppress internal exceptions.

    The wrapper logs a warning when the original emit raises. This prevents
    handler-internal errors from bubbling into application code and ensures
    logging remains best-effort.
    """
    import types as _types

    orig = handler.emit

    def _emit_safe(self, record):
        try:
            return orig(record)
        except Exception:
            try:
                _logging.getLogger(__name__).warning("debug handler emit failed", exc_info=True)
            except Exception:
                _logging.getLogger(__name__).info("Failed to record debug handler emit failure", exc_info=True)

    handler.emit = _types.MethodType(_emit_safe, handler)  # type: ignore[assignment]


# Note: Previously `_maybe_start_exporter` lived in this module as a thin
# wrapper. We prefer calling `start_exporter` directly from `main` to avoid
# unnecessary indirection via wrappers.


if __name__ == "__main__":
    main()
