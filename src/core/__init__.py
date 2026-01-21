"""Core package: main orchestration for the monitoring application.

Exposes the main monitoring loop and emission utilities. Re-exports are
provided to preserve backwards-compatible imports.
"""

from .emitter import emit_snapshot
from .core import run_loop

__all__ = ["emit_snapshot", "run_loop"]
