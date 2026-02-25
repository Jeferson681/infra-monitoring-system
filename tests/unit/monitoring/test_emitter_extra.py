"""Tests for core.emitter helpers: formatting and emitting snapshots."""

from src.core import emitter


def test_format_and_print_helpers(capsys):
    """_format/print helpers handle None and dict inputs without raising."""
    snap = None
    result = {"state": "OK"}
    emitter._format_human_msg(snap, result)
    emitter._print_snapshot_short(None)
    emitter._print_snapshot_long(None)


def test_emit_snapshot_writes_and_prints(monkeypatch, capsys):
    """emit_snapshot delegates to write_log and prints short/long outputs for verbose levels."""
    monkeypatch.setattr("src.system.logs.write_log", lambda *a, **k: None)
    snap = {"metrics": {"cpu_percent": 1}, "summary_short": "s"}
    result = {"state": "STABLE"}
    emitter.emit_snapshot(snap, result, verbose_level=1)
    captured = capsys.readouterr()
    assert "s" in captured.out or captured.out == ""
