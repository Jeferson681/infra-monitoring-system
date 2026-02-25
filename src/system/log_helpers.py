"""Compatibility shim for :pymod:`src.system.log_helpers`.

Prefer :pymod:`infra_monitoring.infra.system.log_helpers`.
"""

from __future__ import annotations

import importlib as _importlib
import sys as _sys

_new_module = _importlib.import_module("infra_monitoring.infra.system.log_helpers")
_sys.modules[__name__] = _new_module
