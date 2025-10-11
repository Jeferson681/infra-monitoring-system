"""Helpers genéricos de sistema.

Mantido intencionalmente pequeno e sem dependências pesadas.
"""

# vulture: ignore

import logging
import os
import socket
from typing import List, Tuple

logger = logging.getLogger(__name__)


def reap_children_nonblocking() -> List[Tuple[int, int]]:
    """Recolha processos filhos terminados de forma não bloqueante (POSIX).

    Retorna uma lista de tuplas (pid, status) dos processos recolhidos. Em
    plataformas não-POSIX retorna lista vazia.
    """
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
    """Validate um par host:port para uso em conexões de rede.

    Retorna True quando `host` for um endereço IPv4 válido e a porta estiver
    no intervalo (1..65535).
    """
    try:
        socket.inet_aton(host)
        return 0 < port < 65536
    except (OSError, ValueError):
        return False


def _disk_candidate_paths() -> list[object]:
    """Retorne candidatos para checagem de uso de disco.

    Compatível com a lógica usada nos coletores: tenta `Path().anchor` quando
    disponível, depois `Path('/')` e o literal `'/'` como fallback.
    """
    from pathlib import Path

    candidates: list[object] = []
    try:
        anchor = Path().anchor
        if anchor:
            candidates.append(Path(anchor))
    except Exception:  # nosec B110 - best-effort fallback for Path.anchor access
        # The code intentionally ignores errors here and falls back to '/'
        pass
    candidates.append(Path("/"))
    candidates.append("/")
    return candidates
