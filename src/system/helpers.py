"""Helpers genéricos de sistema de ficheiros usados pelo subsistema de logs.

Mantido intencionalmente pequeno e sem dependências para que possa ser
reutilizado por outros módulos.
"""

import logging
import re
import socket

# Reexporta helpers específicos de logging de system.log_helpers para manter uma
# fonte única de verdade para o comportamento de logging, preservando
# compatibilidade para código que importa de system.helpers.

logger = logging.getLogger(__name__)


def parse_ping_output(output: str, is_windows: bool = True) -> float:
    """Extrai o tempo de resposta (ms) a partir do output do comando ping.

    A função lida com formatos do Windows e Unix. Retorna -1.0 se não for
    possível extrair um valor.
    """
    if is_windows:
        # O output do Windows pode conter 'Tempo=12ms' ou 'time=12ms' dependendo
        # da localidade. Buscamos dígitos seguidos de 'ms'.
        match = re.search(r"(?:Tempo|time)[=:]?\s*(\d+)ms", output)
        if match:
            return float(match.group(1))
    else:
        match = re.search(r"time=([0-9.]+) ms", output)
        if match:
            return float(match.group(1))
    return -1.0


def validate_host_port(host: str, port: int) -> bool:
    """Valida se o host e porta são utilizáveis para conexão TCP."""
    try:
        socket.inet_aton(host)
        if not (0 < port < 65536):
            return False
        return True
    except Exception:
        return False


# format_date_for_log is re-exported from system.log_helpers above
