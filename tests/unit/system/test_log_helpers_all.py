import os
import time
import importlib

mod = importlib.import_module("src.system.log_helpers")


def test_sanitize_log_name_fallback():
    """Teste para fallback do nome do log."""
    assert mod.sanitize_log_name("") == "debug_log"
    assert mod.sanitize_log_name("normal_name") == "normal_name"


def test_build_json_entry_and_human_line():
    """Teste para construção de entrada JSON e linha humana."""
    js = mod.build_json_entry("2025-01-01T00:00:00", "INFO", "msg", extra={"a": 1})
    assert js["ts"].startswith("2025")
    assert js["level"] == "INFO"
    # build_json_entry uses key 'msg' for the message
    assert js["msg"] == "msg"

    hl = mod.build_human_line("2025-01-01T00:00:00", "WARN", "short", extras={"k": "v"})
    assert "short" in hl


def test_format_date_and_is_older_than(tmp_path):
    """Teste para formatação de data e verificação de arquivo antigo."""
    p = tmp_path / "f.txt"
    p.write_text("x")
    assert isinstance(mod.format_date_for_log(), str)
    assert mod.is_older_than(p, 3600) is False
    # set mtime to old
    old = time.time() - 3600 * 24
    os.utime(p, (old, old))
    assert mod.is_older_than(p, 3600) is True
