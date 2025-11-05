"""Pacote core: orquestração principal do programa.

Contém o loop principal, parsing de argumentos e integração com a UI.

Re-exports para compatibilidade com importações históricas.
"""

from .emitter import emit_snapshot

__all__ = ["emit_snapshot"]
