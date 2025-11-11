import json
import datetime
import logging
import os
import socket
from typing import List, Tuple
from pathlib import Path

"""Helpers genéricos de sistema.
Contém utilitários pequenos e sem dependências pesadas que são usados por
vários subsistemas (validação de host/porta, leitura de .env, caminhos de
disco candidatos, etc.).
"""


def update_network_usage_learning(bytes_sent: int, bytes_recv: int) -> bool:
    """Atualiza o aprendizado de uso de rede e verifica se excede o limite aprendido."""
    record_network_usage(bytes_sent, bytes_recv)
    limit = get_network_limit()
    total = bytes_sent + bytes_recv
    allowed_hour = os.environ.get("NETWORK_TREATMENT_ALLOWED_HOUR")
    current_hour = datetime.datetime.now().hour
    if allowed_hour is None:
        return False
    try:
        allowed_hour_int = int(allowed_hour)
    except Exception:
        allowed_hour_int = None
    if allowed_hour_int is None or current_hour != allowed_hour_int:
        return False
    if total > limit:
        return True
    return False


NETWORK_LEARNING_FILE = Path(".cache/network_usage_learning.json")


def ensure_cache_dir_exists():
    """Garante que o diretório .cache existe."""
    NETWORK_LEARNING_FILE.parent.mkdir(parents=True, exist_ok=True)


NETWORK_LEARNING_WEEKS = 4
NETWORK_DEFAULT_LIMIT = 20 * 1024**3  # 20GB
NETWORK_MARGIN = 0.2  # 20%


def record_network_usage(bytes_sent: int, bytes_recv: int) -> None:
    """Persist network usage for daily learning of automatic limit."""
    today = datetime.date.today().isoformat()
    data = {}
    if NETWORK_LEARNING_FILE.exists():
        try:
            with NETWORK_LEARNING_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[today] = {"bytes_sent": bytes_sent, "bytes_recv": bytes_recv}
    try:
        NETWORK_LEARNING_FILE.parent.mkdir(parents=True, exist_ok=True)
        with NETWORK_LEARNING_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).error("Erro ao salvar dados de rede: %s", exc, exc_info=True)


def get_network_limit() -> int:
    """Retorna o limite atual para bytes_sent/bytes_recv, aprendendo após 4 semanas."""
    if not NETWORK_LEARNING_FILE.exists():
        return NETWORK_DEFAULT_LIMIT
    try:
        with NETWORK_LEARNING_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return NETWORK_DEFAULT_LIMIT
    # Agrupa por semana
    weeks: dict[tuple[int, int], list[int]] = {}
    for date_str, usage in data.items():
        dt = datetime.date.fromisoformat(date_str)
        year_week = dt.isocalendar()[:2]
        if year_week not in weeks:
            weeks[year_week] = []
        weeks[year_week].append(usage["bytes_sent"] + usage["bytes_recv"])
    if len(weeks) < NETWORK_LEARNING_WEEKS:
        return NETWORK_DEFAULT_LIMIT
    # Calcula média semanal
    all_values = [v for week in weeks.values() for v in week]
    avg = sum(all_values) / max(1, len(all_values))
    limit = int(avg * (1 + NETWORK_MARGIN))
    return limit


# vulture: ignore

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
    # Path is already imported at module level

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
    # Path is already imported at module level

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


def read_jsonl(path: Path | str, use_lock: bool = False) -> list[dict]:
    """Lê um arquivo .jsonl e retorna uma lista de dicts. Usa portalocker se solicitado."""
    p = Path(path)
    entries = []
    portalocker = None
    if use_lock:
        try:
            import portalocker as _portalocker

            portalocker = _portalocker
        except ImportError:
            pass

    def _parse_jsonl_lines(fh):
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception as exc:
                logging.warning(f"Linha JSON inválida ignorada: {exc}")

    try:
        if use_lock and portalocker:
            with portalocker.Lock(str(p), "r", encoding="utf-8") as fh:
                _parse_jsonl_lines(fh)
        else:
            with p.open("r", encoding="utf-8") as fh:
                _parse_jsonl_lines(fh)
    except OSError:
        return []
    return entries


def merge_env_items(env_path: Path, process_env: dict) -> dict:
    """Mescla itens de um ficheiro `.env` com o ambiente de processo.

    O mapeamento `process_env` (normalmente ``os.environ``) sobrescreve as
    chaves do ficheiro. A função não tem efeitos colaterais.
    """
    file_items = read_env_file(env_path)
    # Fazer uma cópia para evitar mutação dos inputs
    out = dict(file_items)
    out.update(dict(process_env))
    return out
