"""Compatibility shim for :pymod:`src.exporter.prometheus`.

Prefer :pymod:`infra_monitoring.api.exporter.prometheus`.
"""

from __future__ import annotations

import importlib as _importlib
import sys as _sys

_new_module = _importlib.import_module("infra_monitoring.api.exporter.prometheus")
_sys.modules[__name__] = _new_module
