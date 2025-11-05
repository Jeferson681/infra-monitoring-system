import os
import socket
import subprocess
from pathlib import Path
import tempfile

from src.system import treatments as tr


def test_platform_candidates():
    """Teste para candidatos de plataforma."""
    assert isinstance(tr._platform_candidates("linux"), list)
    assert isinstance(tr._platform_candidates("win32"), list)
    assert isinstance(tr._platform_candidates("darwin"), list)
    assert tr._platform_candidates("unknown") == []


def test_online_check_fails(monkeypatch):
    """Teste para falha de verificação online."""

    # simulate socket.create_connection raising
    def fake_create(*a, **kw):
        raise OSError("no net")

    monkeypatch.setattr(socket, "create_connection", fake_create)
    assert tr._online_check(timeout=0.01) is False


def test_reapply_network_config_no_candidates(monkeypatch):
    """Teste para reconfiguração de rede sem candidatos."""
    monkeypatch.setattr(tr, "_platform_candidates", lambda p: [])
    # Should return early and not raise
    tr.reapply_network_config()


def test_reapply_network_config_runs_commands(monkeypatch):
    """Teste para reconfiguração de rede executando comandos."""
    # Provide one candidate and pretend shutil.which exists
    monkeypatch.setattr(tr, "_platform_candidates", lambda p: [["echo", "ok"]])
    monkeypatch.setattr(tr.shutil, "which", lambda c: "/bin/echo")

    # patch subprocess.run to simulate a failing then a succeeding online check
    class FakeProc:
        def __init__(self, rc=0):
            self.returncode = rc

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeProc(0))
    monkeypatch.setattr(tr, "_online_check", lambda timeout=2.0: True)

    tr.reapply_network_config()


def test_iter_roots_on_windows_and_posix(monkeypatch, tmp_path):
    """Teste para iteração de roots em Windows e POSIX."""
    # on POSIX
    monkeypatch.setattr(os, "name", "posix", raising=False)
    roots = tr._iter_roots()
    assert roots == [Path("/")]

    # on Windows emulate C: exists
    monkeypatch.setattr(os, "name", "nt", raising=False)
    monkeypatch.setattr(Path, "exists", lambda self: True)
    roots2 = tr._iter_roots()
    assert isinstance(roots2, list)


def test_check_disk_usage_handles_errors(monkeypatch, tmp_path):
    """Teste para verificação de uso de disco lidando com erros."""
    # simulate _iter_roots returning path that raises on exists
    monkeypatch.setattr(tr, "_iter_roots", lambda: [Path("/weird")])

    def fake_exists(self):
        raise OSError("boom")

    monkeypatch.setattr(Path, "exists", fake_exists)
    res = tr.check_disk_usage(90)
    assert res == []


def test_trim_reap_zombie_on_platform(monkeypatch):
    """Teste para reap de processos zumbis na plataforma."""
    monkeypatch.setattr(os, "name", "posix", raising=False)
    # patch reap_children_nonblocking to raise
    monkeypatch.setattr(tr, "reap_children_nonblocking", lambda: [])
    assert tr.reap_zombie_processes() == 0


def test_cleanup_temp_files_handles_oserror(monkeypatch, tmp_path):
    """Teste para limpeza de arquivos temporários lidando com OSError."""
    # simulate tempfile.gettempdir pointing to our tmp_path
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    # make it raise on iterdir
    monkeypatch.setattr(Path, "iterdir", lambda self: (_ for _ in ()).throw(OSError("boom")))
    # should not raise
    tr.cleanup_temp_files()
