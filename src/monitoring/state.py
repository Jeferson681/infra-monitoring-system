"""Compatibility shim for :pymod:`src.monitoring.state`.

Prefer :pymod:`infra_monitoring.services.monitoring.state`.
"""

from __future__ import annotations

import importlib as _importlib
import sys as _sys

_new_module = _importlib.import_module("infra_monitoring.services.monitoring.state")
_sys.modules[__name__] = _new_module
