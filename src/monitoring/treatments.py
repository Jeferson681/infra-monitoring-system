"""Compatibility shim: re-export treatments from src.system.treatments.

Some tests and older call-sites expect a module at `src.monitoring.treatments`.
Keep this shim minimal and import implementation from the canonical location.
"""

from ..system.treatments import *  # noqa: F401,F403

__all__ = [name for name in dir() if not name.startswith("__")]
