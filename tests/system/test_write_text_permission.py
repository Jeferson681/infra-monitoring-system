def test_write_text_permission_error(monkeypatch, tmp_path):
    """Simula PermissionError ao abrir arquivo e verifica que write_text retorna False.

    Em vez de alterar permissões do SO (problemático no Windows CI), monkeypatch
    `Path.open` para lançar PermissionError quando chamado.
    """
    # Monkeypatch Path.open to raise PermissionError (cross-platform-friendly)
    import pathlib

    def _open_raise(self, *args, **kwargs):
        raise PermissionError("simulated-denied")

    monkeypatch.setattr(pathlib.Path, "open", _open_raise, raising=True)

    from src.system.log_helpers import write_text

    path = tmp_path / "log" / "f.log"
    ok = write_text(path, "teste")
    assert ok is False
