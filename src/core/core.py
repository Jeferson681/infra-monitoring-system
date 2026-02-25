"""Compatibility shim for :pymod:`src.core.core`.

Prefer :pymod:`infra_monitoring.core.core`.
"""

from __future__ import annotations

import sys as _sys

from infra_monitoring.core import core as _new_module

_sys.modules[__name__] = _new_module
