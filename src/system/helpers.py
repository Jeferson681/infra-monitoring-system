"""Helpers genéricos de sistema.

Contém utilitários pequenos e sem dependências pesadas que são usados por
vários subsistemas (validação de host/porta, leitura de .env, caminhos de
disco candidatos, etc.).
"""

# vulture: ignore

import logging
import os
import socket
from typing import List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


def reap_children_nonblocking() -> List[Tuple[int, int]]:
    """Recolha processos filhos terminados de forma não bloqueante (POSIX).

    Retorna:
        Lista de tuplas (pid, status) dos processos recolhidos. Em plataformas
        não-POSIX retorna lista vazia.
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
    """Valida um par host:port para uso em conexões de rede.

    Retorna True quando ``host`` for um endereço IPv4 válido e a porta estiver
    no intervalo (1..65535).
    """
    try:
        socket.inet_aton(host)
        return 0 < port < 65536
    except (OSError, ValueError):
        return False


def _disk_candidate_paths() -> list[object]:
    r"""Retorne candidatos para checagem de uso de disco.

    A lista gerada tenta usar a âncora do sistema (ex: "C:\\" no Windows),
    depois o root POSIX e, por fim, o literal '/', como fallback.
    """
    from pathlib import Path

    candidates: list[object] = []
    try:
        anchor = Path().anchor
        if anchor:
            candidates.append(Path(anchor))
    except Exception:  # nosec B110 - best-effort fallback for Path.anchor access
        # Intencional: ignoramos erros aqui e usamos '/' como fallback
        pass
    candidates.append(Path("/"))
    candidates.append("/")
    return candidates


def read_env_file(path: Path | str) -> dict:
    """Leia um ficheiro `.env` simples e retorne um dicionário key->value.

    Regras:
    - Linhas vazias e que começam com '#' são ignoradas.
    - A primeira '=' separa chave/valor; aspas simples ou duplas em torno do
      valor são removidas.
    - Se o ficheiro não existir, retorna um dict vazio.
    """
    from pathlib import Path

    result: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return result
    try:
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                # remover espaços e aspas ao redor
                val = val.strip().strip('"').strip("'")
                # remover comentários inline após o valor (ex: "7  # default")
                if "#" in val:
                    val = val.split("#", 1)[0].rstrip()
                result[key] = val
    except OSError:
        # Best-effort: return empty mapping on read errors
        return {}
    return result


def merge_env_items(env_path: Path, process_env: dict) -> dict:
    """Mescla itens de um ficheiro `.env` com o ambiente de processo.

    O mapeamento `process_env` (normalmente ``os.environ``) sobrescreve as
    chaves do ficheiro. A função não tem efeitos colaterais.
    """
    file_items = read_env_file(env_path)
    # Fazer uma cópia para evitar mutação dos inputs
    out = dict(file_items)
    try:
        out.update(dict(process_env))
    except Exception:
        # Se process_env não for um mapeamento, ignorar e retornar os itens do ficheiro
        return out
    return out
