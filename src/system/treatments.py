"""Tratamentos automáticos simples (memória, rede, disco, logs)."""

from __future__ import annotations
import logging
import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import List
import string
import sys

from system.log_helpers import process_temp_item
from system.helpers import reap_children_nonblocking

logger = logging.getLogger(__name__)


def cleanup_temp_files(days: int = 7) -> None:
    """Remove arquivos temporários antigos."""
    tmpdir = Path(tempfile.gettempdir())
    max_age = days * 86400
    if not tmpdir.exists():
        logger.debug("cleanup_temp_files: tempdir %s does not exist", tmpdir)
        return

    try:
        for item in sorted(tmpdir.iterdir()):
            process_temp_item(item, max_age)
    except OSError as exc:
        # Be conservative: log and don't raise when scanning tempdir fails
        logger.debug("cleanup_temp_files: scanning %s failed: %s", tmpdir, exc, exc_info=True)


def check_disk_usage(threshold_pct: int = 90) -> List[str]:
    """Verifica uso de disco e alerta se acima do limite.

    Retorna lista de mensagens com problemas encontrados.
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
        logger.warning("Disco: %s", i)
    return issues


def _disk_usage_pct(r: Path) -> int:
    """Retorna a percentagem usada do filesystem em `r` como inteiro.

    Lança a exceção do `shutil.disk_usage` para ser tratada pelo chamador.
    """
    usage = shutil.disk_usage(r)
    return int((usage.used / usage.total * 100) if usage.total else 0)


def _iter_roots() -> list[Path]:
    """Retorna lista de raízes a verificar para uso de disco.

    Em Windows retorna todas as letras de drive; em outros sistemas retorna
    a raiz '/'.
    """
    if os.name == "nt":
        # Retornar apenas as letras que existem no sistema para evitar
        # iterações inúteis sobre drives inexistentes.
        roots: list[Path] = []
        for d in string.ascii_uppercase:
            p = Path(f"{d}:/")
            if p.exists():
                roots.append(p)
        return roots or [Path("/")]
    return [Path("/")]


def trim_process_working_set_windows(pid: int) -> bool:
    """Tenta reduzir memória de um processo no Windows (EmptyWorkingSet)."""
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
        logger.debug("trim_process_working_set_windows falhou: %s", exc, exc_info=True)
        return False


def reap_zombie_processes() -> int:
    """Recolhe processos zumbis (POSIX)."""
    if os.name != "posix":
        return 0
    try:
        reaped = reap_children_nonblocking()
    except Exception as exc:
        logger.debug("cleanup_processes: reap falhou: %s", exc, exc_info=True)
        return 0
    count = len(reaped)
    if count:
        logger.info("Recolhidos %d processos", count)
    return count


def reapply_network_config() -> None:
    """Tenta restaurar conectividade de rede (Linux/Win/mac).

    Usa `_platform_candidates` para obter comandos por plataforma e
    `_online_check` para verificar conectividade; pula comandos
    inexistentes e interrompe cedo quando a rede volta.
    """
    if _online_check():
        return

    candidates = _platform_candidates(sys.platform)
    if not candidates:
        logger.debug("reapply_network_config: no candidate commands for platform %s", sys.platform)
        logger.warning("Não foi possível restaurar rede")
        return

    for cmd in candidates:
        if shutil.which(cmd[0]) is None:
            logger.debug("reapply_network_config: command not found, skipping %s", cmd[0])
            continue

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except (subprocess.SubprocessError, OSError) as exc:
            logger.debug("reapply_network_config: %s falhou: %s", cmd, exc, exc_info=True)
            continue

        logger.debug("reapply_network_config: %s => %s", cmd, getattr(proc, "returncode", None))
        if _online_check():
            logger.info("Rede restaurada após %s", cmd)
            return

    logger.warning("Não foi possível restaurar rede")


def _platform_candidates(p: str) -> list:
    """Retorna lista de comandos candidatos por plataforma."""
    p = (p or "").lower()
    if p.startswith("linux"):
        return [["resolvectl", "flush-caches"], ["nmcli", "networking", "on"]]
    if p == "win32":
        return [["ipconfig", "/flushdns"]]
    if p == "darwin":
        return [["dscacheutil", "-flushcache"]]
    return []


def _online_check(timeout: float = 2.0) -> bool:
    """Verifica conectividade exterior com timeout curto."""
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=timeout):
            return True
    except OSError:
        return False


# Reminder: tratamentos que serão usados pela orquestração futura

# cleanup_temp_files
# check_disk_usage
# trim_process_working_set_windows
# reap_zombie_processes
# reapply_network_config

# FIM.
