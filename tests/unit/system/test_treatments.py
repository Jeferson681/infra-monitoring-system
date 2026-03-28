import logging
import re


def test_check_disk_usage_and_iter_roots(monkeypatch, tmp_path, caplog):
    """check_disk_usage deve reportar issues quando uso acima do limiar."""
    from infra_monitoring.infra.system import treatments

    # make _iter_roots return our tmp_path and force _disk_usage_pct to a high value
    monkeypatch.setattr(treatments, "_iter_roots", lambda: [tmp_path])
    monkeypatch.setattr(treatments, "_disk_usage_pct", lambda r: 95)
    caplog.set_level(logging.WARNING)
    issues = treatments.check_disk_usage(threshold_pct=90)
    assert isinstance(issues, list)
    assert len(issues) == 1
    assert str(tmp_path) in issues[0]
    assert re.search(r"95% used", issues[0])
    # ensure a warning was logged for the issue
    assert any("Disk usage issue" in rec.getMessage() for rec in caplog.records)


def test_reap_zombie_processes_posix(monkeypatch, caplog):
    """reap_zombie_processes deve chamar reap_children_nonblocking em POSIX."""
    from infra_monitoring.infra.system import treatments

    monkeypatch.setattr(treatments.os, "name", "posix", raising=False)
    monkeypatch.setattr(treatments, "reap_children_nonblocking", lambda: [1, 2, 3])
    caplog.set_level(logging.INFO)
    count = treatments.reap_zombie_processes()
    assert isinstance(count, int) and count == 3
    assert any("Collected 3" in rec.getMessage() for rec in caplog.records)


def test_trim_process_working_set_non_windows(monkeypatch):
    """trim_process_working_set_windows devolve False em não-Windows."""
    from infra_monitoring.infra.system import treatments

    monkeypatch.setattr(treatments.os, "name", "posix", raising=False)
    result = treatments.trim_process_working_set_windows(12345)
    assert isinstance(result, bool) and result is False


def test_cleanup_temp_files(tmp_path, monkeypatch):
    """cleanup_temp_files should call process_temp_item for each temp entry."""
    from infra_monitoring.infra.system.treatments import cleanup_temp_files

    # create temp files in tmp_path and monkeypatch tempfile.gettempdir
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    p = tmp_path / "old.txt"
    p.write_text("x")

    called = []

    def fake_process(item, max_age):
        called.append((item, max_age))

    monkeypatch.setattr(
        "infra_monitoring.infra.system.treatments.process_temp_item", fake_process
    )

    cleanup_temp_files(days=0)
    assert called, "process_temp_item was not called"
    # ensure the path passed matches our temp file and max_age is 0
    assert any(str(p) in str(c[0]) and c[1] == 0 for c in called)


def test_check_disk_usage(monkeypatch, tmp_path):
    """check_disk_usage should report issues when disk usage above threshold."""
    from infra_monitoring.infra.system.treatments import check_disk_usage

    # monkeypatch roots and disk_usage
    monkeypatch.setattr(
        "infra_monitoring.infra.system.treatments._iter_roots", lambda: [tmp_path]
    )

    class DummyUsage:
        def __init__(self, total, used):
            self.total = total
            self.used = used

    monkeypatch.setattr("shutil.disk_usage", lambda p: DummyUsage(100, 95))
    issues = check_disk_usage(threshold_pct=90)
    assert isinstance(issues, list)
    assert len(issues) == 1
    assert str(tmp_path) in issues[0]
    assert "95% used" in issues[0]


def test_reapply_network_config_no_candidates(monkeypatch, caplog):
    """reapply_network_config returns cleanly when no platform candidates are present."""
    from infra_monitoring.infra.system.treatments import reapply_network_config

    # force no candidates
    monkeypatch.setattr(
        "infra_monitoring.infra.system.treatments._platform_candidates", lambda p: []
    )
    # ensure online check fails so reapply logic runs
    monkeypatch.setattr(
        "infra_monitoring.infra.system.treatments._online_check",
        lambda timeout=2.0: False,
    )
    caplog.set_level(logging.WARNING)
    reapply_network_config()
    # the function logs a warning when it cannot restore connectivity
    assert any(
        "Could not restore network connectivity" in rec.getMessage()
        for rec in caplog.records
    )
