"""Compatibility shim for :pymod:`src.exporter.main_http`.

Prefer :pymod:`infra_monitoring.api.exporter.main_http`.
"""

from __future__ import annotations

import sys as _sys

from infra_monitoring.api.exporter import main_http as _new_module

_sys.modules[__name__] = _new_module
