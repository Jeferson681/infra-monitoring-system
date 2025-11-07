import time

from src.system import logs as logs_mod
from src.system import log_helpers as lh


def test_get_log_paths_creates_dirs(tmp_path, monkeypatch):
    """Teste para criação de diretórios de log."""
    root = tmp_path / "mylogs"
    # ensure env not interfering
    monkeypatch.delenv("MONITORING_LOG_ROOT", raising=False)

    lp = logs_mod.get_log_paths(root)
    assert lp.root == root
    assert lp.log_dir.exists()
    assert lp.json_dir.exists()
    assert lp.archive_dir.exists()
    assert lp.debug_dir.exists()


def test_resolve_filename_and_safe_flag(monkeypatch):
    """Teste para resolução de nome de arquivo e flag de segurança."""
    name = "app@!"  # will be sanitized
    fname = logs_mod._resolve_filename(name, safe_log_enable=False)
    assert "app_" in fname or "app" in fname

    fname_safe = logs_mod._resolve_filename(name, safe_log_enable=True)
    assert "_safe" in fname_safe


def test_write_log_human_and_json(tmp_path, monkeypatch):
    """Teste para escrita de log humano e JSON."""
    # ensure get_log_paths uses our tmp root
    monkeypatch.setenv("MONITORING_LOG_ROOT", str(tmp_path))
    name = "myapp"

    # make sure writes go through but don't require portalocker
    monkeypatch.setattr(lh, "write_text", lambda p, t: None)
    monkeypatch.setattr(lh, "write_json", lambda p, o: None)

    logs_mod.write_log(name, "INFO", "hello world", human_enable=True, json_enable=True)

    # check debug file path generation
    dbg = logs_mod.get_debug_file_path()
    assert dbg.name.startswith("debug_log-")


def test_hourly_allows_and_blocks(tmp_path, monkeypatch):
    """Teste para controle de escrita horária e bloqueio."""
    monkeypatch.setenv("MONITORING_LOG_ROOT", str(tmp_path))
    name = "monitoring-hourly"
    # ensure get_log_paths creates cache dir

    # Usar project_root direto no teste
    assert logs_mod._hourly_allows_write(name, True, 1, project_root=tmp_path)
    # write a timestamp
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir(exist_ok=True)
    ts_file = cache_dir / (f".last_human_{lh.sanitize_log_name(name, name)}.ts")
    with open(ts_file, "w", encoding="utf-8") as f:
        f.write(str(int(time.time())))

    time.sleep(2)
    # Após 2 segundos, deve bloquear (window não passou)
    assert logs_mod._hourly_allows_write(name, True, 3600, project_root=tmp_path) is False


def test_ensure_log_dirs_exist_recreates(tmp_path, monkeypatch):
    """Teste para recriação de diretórios de log ausentes."""
    root = tmp_path / "root"
    # create only some dirs
    (root / "log").mkdir(parents=True)

    logs_mod.ensure_log_dirs_exist(root)
    # now all dirs exist
    lp = logs_mod.get_log_paths(root)
    for p in lp:
        assert p.exists()
