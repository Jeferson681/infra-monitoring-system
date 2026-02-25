"""Compatibility shim for :pymod:`src.monitoring.handlers`.

Prefer :pymod:`infra_monitoring.services.monitoring.handlers`.
"""

from __future__ import annotations

import sys as _sys

from infra_monitoring.services.monitoring import handlers as _new_module

_sys.modules[__name__] = _new_module
