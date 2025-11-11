"""Leitores resilientes para arquivos JSONL (linha-delimitados).

Fornece utilitários para iterar sobre arquivos JSONL, incluindo suporte a
arquivos gzip e estratégias para lidar com gravações parciais (p.ex. quando
um produtor ainda está escrevendo). O código evita lançar exceções em casos
comuns (linhas vazias, JSON inválido) e permite um modo "tail -f" com
retries/backoff leves.

APIs públicas:
- iter_jsonl(path, follow=False, max_retries=3, retry_delay=0.1)
  -> gerador de dicts para cada linha JSON válida encontrada.

O módulo é projetado para ser pequeno, bem testável e sem dependências
externas.
"""

from __future__ import annotations

import gzip
import io
import json
import time
from pathlib import Path
from typing import Generator


def _open_maybe_gzip(path: Path):
    """Abre um arquivo suportando gzip por extensão .gz.

    Retorna um file-like em texto (str). Chamador deve fechar o objeto.
    """
    if str(path).endswith(".gz"):
        # gzip.open produz bytes; abrir em modo texto para facilitar leitura de linhas
        return gzip.open(path, mode="rt", encoding="utf-8", errors="replace")
    return open(path, mode="r", encoding="utf-8", errors="replace")


def iter_jsonl(
    path: str | Path,
    follow: bool = False,
    max_retries: int = 3,
    retry_delay: float = 0.1,
) -> Generator[dict, None, None]:
    """Itera sobre um arquivo JSONL e produz objetos Python.

    Args:
        path: caminho para arquivo .jsonl ou .jsonl.gz
        follow: se True, fica aguardando novas linhas (similar a tail -f)
        max_retries: tentativas antes de abandonar leitura em follow=False
        retry_delay: intervalo entre tentativas (segundos)

    Yields:
        dicts decodificados de cada linha JSON válida.

    Notas:
        - Linhas vazias ou que não decodificam como JSON são ignoradas.
        - Em arquivos sendo escritos, parte de uma linha pode aparecer; o
          leitor irá aguardar pequenas janelas quando follow=True.

    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    retries = 0
    with _open_maybe_gzip(p) as fh:
        while True:
            line = fh.readline()
            if not line:
                # EOF atingido
                if follow:
                    # aguardar e tentar novamente
                    time.sleep(retry_delay)
                    retries = 0
                    continue
                if retries < max_retries:
                    retries += 1
                    time.sleep(retry_delay)
                    continue
                break

            retries = 0
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # Linha possivelmente parcial; se estiver no modo follow,
                # aguardar que o restante seja escrito. Caso contrário,
                # ignorar a linha.
                if follow:
                    # retroceder o cursor na linha atual para tentar ler
                    # novamente após pequeno delay.
                    # Nota: apenas possível quando o file object suporta seek().
                    try:
                        pos = fh.tell()
                        # esperar um pouquinho para permitir escrita completa
                        time.sleep(retry_delay)
                        fh.seek(pos)
                        continue
                    except (OSError, io.UnsupportedOperation):
                        # Se não suportar seek (ex.: stream), apenas aguardar
                        time.sleep(retry_delay)
                        continue
                # Fora do modo follow, ignorar linha inválida
                continue
            yield obj


__all__ = ["iter_jsonl"]
