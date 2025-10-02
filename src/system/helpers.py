"""Helpers genéricos de sistema.

Mantido intencionalmente pequeno e sem dependências pesadas.
"""

from __future__ import annotations
import logging
import os
import re
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


def parse_ping_output(output: str, is_windows: bool = True) -> float:
    """Extrai tempo médio de resposta (ms) a partir da saída do `ping`.

    Aceita variações regionais ("Tempo" / "time"), aceita valores com casas
    decimais e ignora case. Retorna -1.0 se não for possível extrair.
    """
    # aceitar floats tanto em Windows quanto em Unix-like; ser case-insensitive
    win_re = re.compile(r"(?:Tempo|time)[=:]?\s*(\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)
    unix_re = re.compile(r"time=(\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)
    if is_windows:
        m = win_re.search(output)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                return -1.0
    else:
        m = unix_re.search(output)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                return -1.0
    return -1.0


def validate_host_port(host: str, port: int) -> bool:
    """Valida host e porta TCP."""
    try:
        socket.inet_aton(host)
        return 0 < port < 65536
    except Exception:
        return False
