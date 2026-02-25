import sys
import types

from src.system import treatments as tr


def test_returns_false_when_not_posix(monkeypatch):
    """When the platform is not POSIX, function should return False."""
    monkeypatch.setattr(tr.os, "name", "nt", raising=False)
    assert tr.trim_process_working_set_posix(12345) is False


def test_posix_malloc_trim_success(monkeypatch):
    """Simulate a POSIX environment where libc.malloc_trim exists and succeeds."""
    monkeypatch.setattr(tr.os, "name", "posix", raising=False)
    monkeypatch.setattr(tr.os, "getpid", lambda: 9999, raising=False)

    fake_ctypes = types.SimpleNamespace()

    def cdll(name):
        class Lib:
            def malloc_trim(self, pad):
                return 1

        return Lib()

    fake_ctypes.CDLL = cdll
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)

    assert tr.trim_process_working_set_posix(9999) is True


def test_posix_no_malloc_trim(monkeypatch):
    """Simulate POSIX but libc has no malloc_trim: should return False."""
    monkeypatch.setattr(tr.os, "name", "posix", raising=False)
    monkeypatch.setattr(tr.os, "getpid", lambda: 1111, raising=False)

    fake_ctypes = types.SimpleNamespace()

    def cdll(name):
        class Lib:
            pass

        return Lib()

    fake_ctypes.CDLL = cdll
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)

    assert tr.trim_process_working_set_posix(1111) is False
