import datetime
import logging
import os
import shutil
import socket
import string
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from .helpers import reap_children_nonblocking, record_network_usage, get_network_limit
from .log_helpers import process_temp_item

logger = logging.getLogger(__name__)


## ...existing code...

_excess_since: Optional[float] = None


def update_network_usage_learning(bytes_sent: int, bytes_recv: int) -> bool:
    """Atualiza o aprendizado de uso de rede e verifica se excede o limite aprendido."""
    record_network_usage(bytes_sent, bytes_recv)
    limit = get_network_limit()
    total = bytes_sent + bytes_recv
    allowed_hour = os.environ.get("NETWORK_TREATMENT_ALLOWED_HOUR")
    current_hour = datetime.datetime.now().hour
    # Persistência do excesso por 5 minutos antes de agir
    now = datetime.datetime.now().timestamp()
    global _excess_since
    if total > limit:
        if _excess_since is None:
            _excess_since = now
        excess_duration = now - _excess_since
    else:
        _excess_since = None
        excess_duration = 0

    # Janela horária configurável
    if allowed_hour is None:
        return False
    try:
        allowed_hour_int = int(allowed_hour)
    except Exception:
        allowed_hour_int = None
    if allowed_hour_int is None or current_hour != allowed_hour_int:
        return False

    # Se excesso persistir por mais de 5min e trava horária ativa, acione tratamento
    if total > limit and excess_duration >= 300:
        try:
            from . import treatments

            restart_func = getattr(treatments, "restart_interface", None)
            if restart_func is not None:
                restart_func()
        except Exception as exc:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning("update_network_usage_learning: restart_interface falhou: %s", exc, exc_info=True)
        return True
    return False


# vulture: ignore
"""Tratamentos automáticos simples (memória, rede, disco, logs)."""


# vulture: ignore
def cleanup_temp_files(days: int = 7) -> None:
    """Remova arquivos temporários antigos do diretório temporário do sistema.

    Varre o diretório temporário do sistema e remove itens cuja idade excede
    `days`. Projetada para ser usada como ação auxiliar de manutenção.
    """
    tmpdir = Path(tempfile.gettempdir())
    max_age = days * 86400
    if not tmpdir.exists():
        logger.debug("cleanup_temp_files: tempdir %s does not exist", tmpdir)
        return

    try:
        for item in sorted(tmpdir.iterdir()):
            process_temp_item(item, max_age)
    except OSError as exc:
        # Log de depuração; não propagar erro em varredura de tempdir
        logger.debug("cleanup_temp_files: scanning %s failed: %s", tmpdir, exc, exc_info=True)


# vulture: ignore
def check_disk_usage(threshold_pct: int = 90) -> List[str]:
    """Verifique o uso de disco e registre/retorne problemas acima do limite.

    Retorna uma lista de mensagens descrevendo volumes cujo uso excede
    `threshold_pct`.
    """
    roots = _iter_roots()
    issues: List[str] = []
    for r in roots:
        try:
            exists = r.exists()
        except OSError:
            # volume inacessível ou sem sistema de ficheiros reconhecido
            continue
        if not exists:
            continue
        try:
            pct = _disk_usage_pct(r)
            if pct >= threshold_pct:
                issues.append(f"{r}: {pct}% usado")
        except Exception as exc:
            issues.append(f"{r}: erro {exc}")
    for i in issues:
        logger.warning("Disk usage issue: %s", i)
    return issues


def _disk_usage_pct(r: Path) -> int:
    """Retorne a percentagem usada do filesystem em `r` como inteiro.

    Lança as exceções de `shutil.disk_usage` para que o chamador possa tratar.
    """
    usage = shutil.disk_usage(r)
    return int((usage.used / usage.total * 100) if usage.total else 0)


def _iter_roots() -> list[Path]:
    """Retorne a lista de raízes a verificar para uso de disco.

    Em Windows retorna as letras de drive existentes; em POSIX retorna ['/'].
    """
    if os.name == "nt":
        # Retornar apenas letras de unidades existentes
        roots: list[Path] = []
        for d in string.ascii_uppercase:
            p = Path(f"{d}:/")
            if p.exists():
                roots.append(p)
        return roots or [Path("/")]
    return [Path("/")]


# vulture: ignore


def trim_process_working_set_windows(pid: int) -> bool:
    """Tente reduzir o working set de um processo no Windows usando EmptyWorkingSet.

    Retorna True em sucesso, False em plataformas não-Windows ou em falha.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes

        PROCESS_SET_QUOTA = 0x0100
        PROCESS_QUERY_INFORMATION = 0x0400

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)

        h = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION, False, pid)
        if not h:
            return False
        try:
            res = psapi.EmptyWorkingSet(h)
            return bool(res)
        finally:
            kernel32.CloseHandle(h)
    except Exception as exc:
        logger.debug("trim_process_working_set_windows failed: %s", exc, exc_info=True)
        return False


def trim_process_working_set_posix(pid: int) -> bool:
    """Best-effort: attempt to reduce a process working set on POSIX systems.

    Notes:
    - Linux/glibc provides ``malloc_trim(0)`` which can release unused heap
      memory back to the kernel, but it only affects the calling process.
    - Trimming another process's working set is not generally possible from
      user-space in a portable, safe way; therefore this function only
      attempts to act when ``pid`` refers to the current process.
    - The operation is best-effort and failures are logged and return False.

    """
    if os.name != "posix":
        return False
    try:
        # Só tenta agir no próprio processo; agir em outro PID não é portátil.
        if int(pid) != os.getpid():
            return False

        import ctypes

        # Tenta referências comuns do libc, depois o namespace do processo.
        for libname in ("libc.so.6", None):
            try:
                libc = ctypes.CDLL(libname) if libname else ctypes.CDLL(None)
            except Exception:
                libc = None
            if not libc:
                continue
            malloc_trim = getattr(libc, "malloc_trim", None)
            if malloc_trim is None:
                continue
            try:
                # chamada: int malloc_trim(size_t pad)
                res = malloc_trim(0)
                return bool(res)
            except Exception as exc:
                logger.debug("trim_process_working_set_posix: malloc_trim falhou: %s", exc, exc_info=True)
                return False
        return False
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("trim_process_working_set_posix erro inesperado: %s", exc, exc_info=True)
        return False


def reap_zombie_processes() -> int:
    """Recolha processos zumbi em plataformas POSIX.

    Retorna o número de processos recolhidos.
    """
    if os.name != "posix":
        return 0
    try:
        reaped = reap_children_nonblocking()
    except Exception as exc:
        logger.debug("cleanup_processes: reap failed: %s", exc, exc_info=True)
        return 0
    count = len(reaped)
    if count:
        logger.info("Collected %d zombie processes", count)
    return count


# vulture: ignore
def reapply_network_config() -> None:
    """Tente restaurar a conectividade de rede executando comandos por plataforma.

    Usa `_platform_candidates` para obter comandos adequados ao sistema e
    `_online_check` para interromper quando a conectividade for restabelecida.
    """
    if _online_check():
        return

    candidates = _platform_candidates(sys.platform)
    if not candidates:
        logger.debug("reapply_network_config: no candidate commands for platform %s", sys.platform)
        logger.warning("Could not restore network connectivity")
        return

    for cmd in candidates:
        if shutil.which(cmd[0]) is None:
            logger.debug("reapply_network_config: command not found, skipping %s", cmd[0])
            continue

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except (subprocess.SubprocessError, OSError) as exc:
            logger.error("reapply_network_config: %s failed: %s", cmd, exc, exc_info=True)
            continue

        logger.debug("reapply_network_config: %s => %s", cmd, getattr(proc, "returncode", None))
        if _online_check():
            logger.info("Network connectivity restored after %s", cmd)
            return

    logger.warning("Could not restore network connectivity")


def _platform_candidates(p: str) -> list:
    """Retorne uma lista de comandos candidatos para restaurar rede, por plataforma."""
    p = (p or "").lower()
    if p.startswith("linux"):
        return [["resolvectl", "flush-caches"], ["nmcli", "networking", "on"]]
    if p == "win32":
        return [["ipconfig", "/flushdns"]]
    if p == "darwin":
        return [["dscacheutil", "-flushcache"]]
    return []


def _online_check(timeout: float = 2.0) -> bool:
    """Verifique conectividade externa tentando abrir conexão TCP com timeout.

    Retorna True se a conexão for bem-sucedida, False em caso contrário.
    """
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=timeout):
            return True
    except OSError:
        return False


# Silence Vulture: these functions are invoked dynamically by
# `monitoring.handlers` via getattr(action_name) at runtime and are
# therefore incorrectly reported as unused by static analyzers.
_VULTURE_KEEP = [
    cleanup_temp_files,
    check_disk_usage,
    trim_process_working_set_windows,
    trim_process_working_set_posix,
    reap_zombie_processes,
    reapply_network_config,
]
