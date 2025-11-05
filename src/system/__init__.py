"""Pacote system: funções de suporte, tratamentos automáticos e logs.

Inclui helpers de sistema, rotação/compressão de logs e ações automáticas.

Re-exports úteis para compatibilidade com imports antigos.
"""

from .log_helpers import build_human_line, write_text, write_json

__all__ = ["build_human_line", "write_text", "write_json"]
