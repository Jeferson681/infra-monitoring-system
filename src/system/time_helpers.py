"""Compatibility shim for :pymod:`src.system.time_helpers`.

Prefer :pymod:`infra_monitoring.infra.system.time_helpers`.
"""

from __future__ import annotations

import sys as _sys

from infra_monitoring.infra.system import time_helpers as _new_module

_sys.modules[__name__] = _new_module
