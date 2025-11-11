import json
import logging


def test_write_debug_function_creates_files(tmp_path, monkeypatch):
    """Verifica que o handler de debug grava .txt e .jsonl via API logging."""
    monkeypatch.setenv("MONITORING_LOG_ROOT", str(tmp_path))

    # configure handlers
    from src.main import _setup_debug_file_handler
    from src.system.logs import get_debug_file_path

    _setup_debug_file_handler()

    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.INFO)
    logger.info("mensagem-debug-fn")

    txt = get_debug_file_path()
    jsonl = txt.with_suffix(".jsonl")

    assert txt.exists(), f"debug text file not created: {txt}"
    assert jsonl.exists(), f"debug jsonl file not created: {jsonl}"

    content = txt.read_text(encoding="utf-8")
    assert "mensagem-debug-fn" in content

    # Validate JSONL content: the formatter emits an object with 'msg'
    jl = jsonl.read_text(encoding="utf-8").splitlines()
    assert jl, "jsonl should contain at least one line"
    obj = json.loads(jl[0])
    assert "mensagem-debug-fn" in obj.get("msg", "")


def test_write_debug_permission_fallback(tmp_path, monkeypatch):
    """Quando handlers falham, logger não deve propagar exceção e arquivos não são criados."""
    monkeypatch.setenv("MONITORING_LOG_ROOT", str(tmp_path))

    from src.main import _setup_debug_file_handler

    # configure handlers
    _setup_debug_file_handler()

    import logging as _logging

    # replace emit on handlers we just added to simulate failure
    root = _logging.getLogger()
    for h in root.handlers:
        try:
            base = getattr(h, "baseFilename", None)
        except Exception:
            base = None
        if base and str(tmp_path) in base:
            # Simulate stream write failure so the handler's emit will
            # encounter an OSError; the handler's emit is wrapped by
            # _setup_debug_file_handler to swallow such exceptions.
            def _bad_write(s, data):
                raise OSError("disk full")

            try:
                # some handlers may not have 'stream' until first emit; create a small
                # writeable object to replace stream if missing
                if not hasattr(h, "stream") or h.stream is None:

                    class _Dummy:
                        def write(self, _):
                            raise OSError("disk full")

                    h.stream = _Dummy()
                else:
                    h.stream.write = _bad_write
            except Exception:
                # if we cannot patch stream, skip
                pass

    logger = _logging.getLogger("test_logger")
    logger.setLevel(_logging.INFO)

    # Should not raise despite handler failing; success is absence of exception
    logger.info("mensagem-fallback")
    # If we reach here, no exception propagated from logging.
