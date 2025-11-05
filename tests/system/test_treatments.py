def test_check_disk_usage_and_iter_roots(monkeypatch, tmp_path):
    """check_disk_usage deve reportar issues quando uso acima do limiar."""
    from src.system import treatments

    # make _iter_roots return our tmp_path and force _disk_usage_pct to a high value
    monkeypatch.setattr(treatments, "_iter_roots", lambda: [tmp_path])
    monkeypatch.setattr(treatments, "_disk_usage_pct", lambda r: 95)
    issues = treatments.check_disk_usage(threshold_pct=90)
    assert issues and isinstance(issues, list)


def test_reap_zombie_processes_posix(monkeypatch):
    """reap_zombie_processes deve chamar reap_children_nonblocking em POSIX."""
    from src.system import treatments

    monkeypatch.setattr(treatments.os, "name", "posix", raising=False)
    monkeypatch.setattr(treatments, "reap_children_nonblocking", lambda: [1, 2, 3])
    count = treatments.reap_zombie_processes()
    assert count == 3


def test_trim_process_working_set_non_windows(monkeypatch):
    """trim_process_working_set_windows devolve False em não-Windows."""
    from src.system import treatments

    monkeypatch.setattr(treatments.os, "name", "posix", raising=False)
    assert treatments.trim_process_working_set_windows(12345) is False


def test_cleanup_temp_files(tmp_path, monkeypatch):
    """cleanup_temp_files should scan tempdir and not raise."""
    from src.system.treatments import cleanup_temp_files

    # create temp files in tmp_path and monkeypatch tempfile.gettempdir
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    p = tmp_path / "old.txt"
    p.write_text("x")
    # ensure process_temp_item runs without raising
    cleanup_temp_files(days=0)


def test_check_disk_usage(monkeypatch, tmp_path):
    """check_disk_usage should report issues when disk usage above threshold."""
    from src.system.treatments import check_disk_usage

    # monkeypatch roots and disk_usage
    monkeypatch.setattr("src.system.treatments._iter_roots", lambda: [tmp_path])

    class DummyUsage:
        def __init__(self, total, used):
            self.total = total
            self.used = used

    monkeypatch.setattr("shutil.disk_usage", lambda p: DummyUsage(100, 95))
    issues = check_disk_usage(threshold_pct=90)
    assert len(issues) >= 1


def test_reapply_network_config_no_candidates(monkeypatch):
    """reapply_network_config returns cleanly when no platform candidates are present."""
    from src.system.treatments import reapply_network_config

    # force no candidates
    monkeypatch.setattr("src.system.treatments._platform_candidates", lambda p: [])
    # ensure returns without exception
    reapply_network_config()
