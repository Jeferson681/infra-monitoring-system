"""Compatibility shim for :pymod:`src.exporter.promtail`.

Prefer :pymod:`infra_monitoring.api.exporter.promtail`.
"""

from __future__ import annotations

import sys as _sys

from infra_monitoring.api.exporter import promtail as _new_module

_sys.modules[__name__] = _new_module
