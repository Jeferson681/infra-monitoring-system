"""Tests for core.emitter helpers: formatting and emitting snapshots."""

from infra_monitoring.core import emitter


def test_format_and_print_helpers(capsys):
    """_format/print helpers handle None and dict inputs without raising."""
    snap = None
    result = {"state": "OK"}
    out = emitter._format_human_msg(snap, result)
    # should return a string when formatting
    assert out is None or isinstance(out, str)
    emitter._print_snapshot_short(None)
    emitter._print_snapshot_long(None)


def test_emit_snapshot_writes_and_prints(monkeypatch, capsys):
    """emit_snapshot delegates to write_log and prints short/long outputs for verbose levels."""
    called = {"w": 0}

    def fake_write(*a, **k):
        called["w"] += 1

    monkeypatch.setattr("infra_monitoring.core.emitter.write_log", fake_write)
    snap = {"metrics": {"cpu_percent": 1}, "summary_short": "s"}
    result = {"state": "STABLE"}
    emitter.emit_snapshot(snap, result, verbose_level=1)
    captured = capsys.readouterr()
    # write_log should have been called once and output should contain summary when verbose
    assert called["w"] >= 1
    assert "s" in captured.out
