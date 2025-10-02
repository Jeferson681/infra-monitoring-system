"""Entrypoint do programa de monitorização.

Move a inicialização (parsing de args, configuração de logging, handler de debug)
para este módulo para que `core` exponha apenas lógica de runtime.
"""

from core.args import parse_args, get_log_config
import logging as _logging
import sys
from system.logs import get_debug_file_path
from core.core import _run_loop


def main(argv: list[str] | None = None) -> None:
    """Inicializa logging e inicia o loop principal do programa."""
    args = parse_args(argv)
    log_conf = get_log_config(args)

    level = getattr(_logging, log_conf.get("level", "WARNING"), _logging.WARNING)
    _logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
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
            except Exception as exc:
                _logging.getLogger(__name__).debug("error inspecting handler: %s", exc)
        if not existing:
            root.addHandler(fh)

        def _exc_hook(exc_type, exc_value, exc_tb):
            try:
                root.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
            except Exception:
                sys.__excepthook__(exc_type, exc_value, exc_tb)

        sys.excepthook = _exc_hook
    except Exception:
        _logging.getLogger(__name__).debug("Could not set up debug file handler")

    _run_loop(interval=args.interval, cycles=args.cycles, verbose_level=getattr(args, "verbose", 0) or 0)


if __name__ == "__main__":
    main()
