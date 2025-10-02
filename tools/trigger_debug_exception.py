# quick test script: attach a debug FileHandler and raise an exception
import sys
import logging

# ensure project src is importable when running via PYTHONPATH in the shell
from system.logs import get_debug_file_path


def setup_and_raise():
    debug_path = get_debug_file_path()
    fh = logging.FileHandler(str(debug_path), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh.setFormatter(fmt)
    root = logging.getLogger()
    root.addHandler(fh)

    def _exc_hook(exc_type, exc_value, exc_tb):
        try:
            root.error("Unhandled exception (test)", exc_info=(exc_type, exc_value, exc_tb))
        except Exception:
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _exc_hook

    # raise an unhandled exception
    raise RuntimeError("test-exception-for-debug-file")


if __name__ == "__main__":
    setup_and_raise()
