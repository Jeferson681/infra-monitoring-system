import importlib


def test_format_human_fallback(monkeypatch):
    """If format_snapshot_human raises, fallback should return a minimal state string."""
    fake = importlib.import_module("src.core.emitter")

    # monkeypatch format_snapshot_human to raise
    monkeypatch.setattr("src.core.emitter.format_snapshot_human", lambda s, r: (_ for _ in ()).throw(Exception("boom")))

    res = fake._format_human_msg(None, {"state": "CRITICAL"})
    assert "state=CRITICAL" in res


def test_emit_snapshot_writes_json(monkeypatch):
    """emit_snapshot should call write_log to persist JSON feed."""
    mod = importlib.reload(importlib.import_module("src.core.emitter"))
    calls = {}

    def fake_write_log(name, level, message, **kwargs):
        calls["called"] = True
        calls["name"] = name
        calls["msg"] = message

    monkeypatch.setattr("src.core.emitter.write_log", fake_write_log)

    # should not raise
    mod.emit_snapshot({"state": "STABLE"}, {"state": "STABLE"}, verbose_level=0)
    assert calls.get("called") is True
    assert calls.get("name") == "monitoring"


def test_print_short_and_long(capsys):
    """Validates short and long snapshot printing to stdout."""
    mod = importlib.reload(importlib.import_module("src.core.emitter"))

    # short: snapshot with summary_short
    snap = {"summary_short": "quick summary"}
    mod._print_snapshot_short(snap)
    out = capsys.readouterr().out
    assert "quick summary" in out

    # long: snapshot with summary_long list
    snap2 = {"summary_long": ["line1", "line2"]}
    mod._print_snapshot_long(snap2)
    out2 = capsys.readouterr().out
    assert "line1" in out2 and "line2" in out2
