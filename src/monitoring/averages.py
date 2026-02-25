"""Compatibility shim for :pymod:`src.monitoring.averages`.

Prefer :pymod:`infra_monitoring.services.monitoring.averages`.
"""

from __future__ import annotations

import importlib as _importlib
import sys as _sys

_new_module = _importlib.import_module("infra_monitoring.services.monitoring.averages")
_sys.modules[__name__] = _new_module
