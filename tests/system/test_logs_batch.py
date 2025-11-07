import time
from pathlib import Path


from src.system import logs as logs_mod


def test_get_log_paths_and_dirs(tmp_path, monkeypatch):
    """Teste para obtenção de caminhos e diretórios de log."""
    monkeypatch.setenv("MONITORING_LOG_ROOT", str(tmp_path))
    lp = logs_mod.get_log_paths()
    assert lp.root == Path(str(tmp_path))
    # directories should exist
    assert lp.log_dir.exists()
    assert lp.json_dir.exists()
    assert lp.archive_dir.exists()
    assert lp.debug_dir.exists()
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir(exist_ok=True)
    assert cache_dir.exists()


def test_resolve_filename_and_normalize():
    """Teste para resolução e normalização de nome de arquivo."""
    name = "..bad/name!!"
    fn = logs_mod._resolve_filename(name, safe_log_enable=False)
    assert "-" in fn
    fn2 = logs_mod._resolve_filename(name, safe_log_enable=True)
    assert "_safe" in fn2


def test_normalize_messages_and_extras():
    """Teste para normalização de mensagens e extras."""
    assert logs_mod._normalize_messages("a") == ["a"]
    assert logs_mod._normalize_messages(["a", "b"]) == ["a", "b"]

    assert logs_mod._normalize_extras(None, 2) == [None, None]
    assert logs_mod._normalize_extras({"a": 1}, 2) == [{"a": 1}, {"a": 1}]
    assert logs_mod._normalize_extras([{"x": 1}], 2) == [{"x": 1}, None]


def test_write_log_human_and_json(tmp_path, monkeypatch):
    """Teste para escrita de log humano e JSON em lote."""
    # direct writes captured by monkeypatching write_text and write_json
    monkeypatch.setenv("MONITORING_LOG_ROOT", str(tmp_path))
    calls = {"text": [], "json": []}

    def fake_write_text(p, text):
        calls["text"].append((p, text))

    def fake_write_json(p, obj):
        calls["json"].append((p, obj))

    monkeypatch.setattr(logs_mod, "write_text", fake_write_text)
    monkeypatch.setattr(logs_mod, "write_json", fake_write_json)

    # single message
    logs_mod.write_log("app", "INFO", "hello", extra={"k": "v"}, human_enable=True, json_enable=True)
    assert calls["text"] or calls["json"]

    # multiple messages with extras list
    calls["text"].clear()
    calls["json"].clear()
    logs_mod.write_log("app", "INFO", ["a", "b"], extra=[{"i": 1}, {"i": 2}], human_enable=True, json_enable=True)
    assert len(calls["text"]) == 2
    assert len(calls["json"]) == 2


def test_hourly_allows_write_and_perform_human(tmp_path, monkeypatch):
    """Teste para controle de escrita horária e execução humana em lote."""
    monkeypatch.setenv("MONITORING_LOG_ROOT", str(tmp_path))
    name = "mylog"
    # Usar project_root direto no teste
    key = logs_mod.sanitize_log_name(name, name)
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir(exist_ok=True)
    ts_file = cache_dir / f".last_human_{key}.ts"
    ts_file.write_text(str(int(time.time())))
    assert logs_mod._hourly_allows_write(name, True, 3600, project_root=tmp_path) is False

    # old timestamp -> allow
    ts_file.write_text(str(int(time.time()) - 10000))
    assert logs_mod._hourly_allows_write(name, True, 3600, project_root=tmp_path) is True


def test_ensure_log_dirs_exist_creates_missing(tmp_path, monkeypatch):
    """Teste para criação de diretórios de log ausentes."""
    root = tmp_path / "root"
    root.mkdir()
    # create only some dirs
    (root / "log").mkdir()
    # ensure other dirs missing
    # call ensure_log_dirs_exist with this root; it should call get_log_paths and create missing dirs
    logs_mod.ensure_log_dirs_exist(root)
    assert (root / "json").exists()
    assert (root / "archive").exists()
    assert (root / "debug").exists()


def test_rotate_logs_calls_try_rotate(monkeypatch, tmp_path):
    """Teste para rotação de logs e chamada de try_rotate."""
    # create directories and some fake files
    monkeypatch.setenv("MONITORING_LOG_ROOT", str(tmp_path))
    lp = logs_mod.get_log_paths()
    # create fake log and json files
    (lp.log_dir / "a.log").write_text("x")
    (lp.json_dir / "b.jsonl").write_text("y")

    called = []

    def fake_try_rotate(p, archive_dir, gz_suffix, day_secs, week_secs):
        called.append((p.name, gz_suffix))

    monkeypatch.setattr(logs_mod, "try_rotate_file", fake_try_rotate)
    logs_mod.rotate_logs(day_secs=1, week_secs=1)
    assert any(".log" in name or ".jsonl" in name for name, _ in called)
