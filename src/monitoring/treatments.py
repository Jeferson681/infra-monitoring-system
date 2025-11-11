"""Shim de compatibilidade: re-exporta treatments de `src.system.treatments`.

Alguns testes e chamadas antigas esperam um módulo em
`src.monitoring.treatments`. Mantemos este shim mínimo e delegamos a
implementação para o local canónico (`src.system.treatments`).
"""

from ..system.treatments import *  # noqa: F401,F403

__all__ = [name for name in dir() if not name.startswith("__")]
