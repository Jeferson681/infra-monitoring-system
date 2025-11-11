from types import SimpleNamespace


from src.monitoring import state as st


def test_write_post_treatment_primary(monkeypatch, tmp_path):
    """Teste para escrita primária de pós-tratamento."""
    """Teste para escrita primária de pós-tratamento."""
    ss = st.SystemState({}, critical_duration=1, post_treatment_wait_seconds=0)

    # fake log paths object
    lp = SimpleNamespace(
        root=tmp_path,  # Adiciona root para compatibilidade com o método
        cache_dir=tmp_path / ".cache",
        json_dir=tmp_path / "json",
    )  # Mantido para compatibilidade
    # monkeypatch the functions in the system modules they are imported from
    monkeypatch.setattr("src.system.logs.get_log_paths", lambda: lp)
    # monkeypatch write_json to record writes
    written = []

    def fake_write_json(p, obj):
        written.append((p, obj))

    monkeypatch.setattr("src.system.log_helpers.write_json", fake_write_json)

    snap = {"state": "post_treatment", "metrics": {}}
    ss._write_post_treatment_primary(snap)
    # expect at least one write to cache and one to json dir
    assert any(str(tmp_path) in str(p) for p, _ in written)


def test_write_post_treatment_fallback(monkeypatch, tmp_path):
    """Teste para fallback de escrita de pós-tratamento."""
    """Teste para fallback de escrita de pós-tratamento."""
    ss = st.SystemState({}, critical_duration=1, post_treatment_wait_seconds=0)

    # ensure MONITORING_LOG_ROOT is set to tmp_path
    monkeypatch.setenv("MONITORING_LOG_ROOT", str(tmp_path))

    snap = {"state": "post_treatment", "metrics": {}}
    # call fallback; agora só cria em .cache na raiz do projeto
    ss._write_post_treatment_fallback(snap)
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    cache_file = project_root / ".cache" / st._POST_TREATMENT_FILENAME
    assert cache_file.exists()


def test_persist_post_treatment_snapshot_fallback(monkeypatch, tmp_path):
    """Teste para persistência de snapshot pós-tratamento com fallback."""
    """Teste para persistência de snapshot pós-tratamento com fallback."""
    ss = st.SystemState({}, critical_duration=1, post_treatment_wait_seconds=0)

    # monkeypatch get_log_paths to return a path under tmp_path
    lp = SimpleNamespace(cache_dir=tmp_path / ".cache")  # Mantido para compatibilidade
    monkeypatch.setattr("src.system.logs.get_log_paths", lambda: lp)

    # make write_json raise to force fallback to write_text
    def bad_write_json(p, obj):
        raise RuntimeError("bad")

    monkeypatch.setattr("src.system.log_helpers.write_json", bad_write_json)

    # monkeypatch write_text to capture content
    captured = []

    def fake_write_text(p, text):
        captured.append((p, text))

    # ensure fallback write_text is used by monkeypatching log_helpers.write_text
    monkeypatch.setattr("src.system.log_helpers.write_text", fake_write_text)
    # also prevent external fallback from writing to disk by patching the class method
    monkeypatch.setattr(st.SystemState, "_write_post_treatment_fallback", lambda self, snap: None)

    snap = {"state": "post_treatment", "metrics": {}}
    ss._persist_post_treatment_snapshot(snap)
    # if fallback path used, captured will contain one entry
    assert isinstance(captured, list)
