"""Compatibility shim for :pymod:`src.monitoring.formatters`.

Prefer :pymod:`infra_monitoring.services.monitoring.formatters`.
"""

from __future__ import annotations

import sys as _sys

from infra_monitoring.services.monitoring import formatters as _new_module

_sys.modules[__name__] = _new_module
