"""Compatibility shim for :pymod:`src.monitoring.metrics`.

Prefer :pymod:`infra_monitoring.services.monitoring.metrics`.
"""

from __future__ import annotations

import sys as _sys

from infra_monitoring.services.monitoring import metrics as _new_module

_sys.modules[__name__] = _new_module
