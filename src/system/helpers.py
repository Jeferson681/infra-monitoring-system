"""Helpers genéricos de sistema.

Mantido intencionalmente pequeno e sem dependências pesadas.
"""

# vulture: ignore

from __future__ import annotations
import logging
import os
import socket
from typing import List, Tuple

logger = logging.getLogger(__name__)


def reap_children_nonblocking() -> List[Tuple[int, int]]:
    """Recolhe processos filhos terminados (POSIX, não bloqueante)."""
    reaped: List[Tuple[int, int]] = []
    if os.name == "posix":
        try:
            # Alguns analisadores estáticos/mypy reclamam do acesso direto a
            # `os.WNOHANG` em plataformas onde a constante pode não existir.
            # Usamos getattr com fallback para manter o comportamento POSIX
            # e evitar erros de tipagem em outras plataformas.
            flags = getattr(os, "WNOHANG", 1)
            while True:
                pid, status = os.waitpid(-1, flags)
                if pid == 0:
                    break
                reaped.append((pid, status))
        except ChildProcessError:
            pass  # nenhum filho
        except OSError:
            pass  # plataforma ou permissão
    return reaped


def validate_host_port(host: str, port: int) -> bool:
    """Valida host e porta TCP."""
    try:
        socket.inet_aton(host)
        return 0 < port < 65536
    except (OSError, ValueError):
        return False
