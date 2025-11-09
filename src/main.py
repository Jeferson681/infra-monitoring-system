"""Entrypoint do programa de monitorização.

Move a inicialização (parsing de args, configuração de logging, handler de debug)
para este módulo para que `core` exponha apenas lógica de runtime.
"""

from .core.args import parse_args, get_log_config
import logging as _logging
import sys
from .system.logs import get_debug_file_path
from .core.core import _run_loop
import os

# Use existing averages helper to ensure hourly/cache state exists
from .monitoring.averages import ensure_default_last_ts


def main(argv: list[str] | None = None) -> None:
    """Inicializa logging, handlers de debug e inicia o loop principal.

    Parâmetros:
        argv: lista de argumentos (para testes); quando None usa sys.argv.
    """
    # Se nenhum argumento for passado, usa interval=1 e cycles=0 como padrão
    if argv is None or (isinstance(argv, list) and len(argv) == 0):
        argv = ["-i", "1", "-c", "0"]
    args = parse_args(argv)
    log_conf = get_log_config(args)

    level = getattr(_logging, log_conf.get("level", "WARNING"), _logging.WARNING)
    _logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        _setup_debug_file_handler()
    except Exception as exc:
        _logging.getLogger(__name__).debug("falha ao configurar debug file handler: %s", exc, exc_info=True)

    # garantir arquivo de controle (.cache/last_ts.json) antes de iniciar o loop
    try:
        ensure_default_last_ts()
    except Exception:
        _logging.getLogger(__name__).debug("falha ao garantir arquivo de controle no startup", exc_info=True)
    # Optionally start Prometheus exporter if enabled via env
    try:
        from .exporter.prometheus import start_exporter

        if os.getenv("MONITORING_EXPORTER_ENABLE", "0") in ("1", "true", "yes"):
            try:
                start_exporter()
            except Exception:
                _logging.getLogger(__name__).debug("falha ao iniciar exporter Prometheus", exc_info=True)
    except Exception:
        _logging.getLogger(__name__).debug("exporter não disponível", exc_info=True)

    _run_loop(interval=args.interval, cycles=args.cycles, verbose_level=getattr(args, "verbose", 0) or 0)


if __name__ == "__main__":
    main()


def _setup_debug_file_handler() -> None:
    """Configure a debug FileHandler and global exception hook.

    Extracted to reduce complexity of `main`.
    """
    debug_path = get_debug_file_path()
    fh = _logging.FileHandler(str(debug_path), encoding="utf-8")
    fh.setLevel(_logging.ERROR)
    fmt = _logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh.setFormatter(fmt)
    root = _logging.getLogger()
    existing = False
    for h in root.handlers:
        try:
            if isinstance(h, _logging.FileHandler):
                if getattr(h, "baseFilename", None) == getattr(fh, "baseFilename", None):
                    existing = True
                    break
        except Exception:
            _logging.getLogger(__name__).exception("erro inspeccionando handler")
    if not existing:
        root.addHandler(fh)

    def _exc_hook(exc_type, exc_value, exc_tb):
        try:
            root.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        except Exception:
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _exc_hook


# Note: previously `_maybe_start_exporter` lived here as a thin wrapper. Per project
# guideline, we prefer calling `start_exporter` directly from `main` to avoid
# introducing wrapper indirection.
