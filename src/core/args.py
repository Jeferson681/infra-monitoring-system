"""Compatibility shim for :pymod:`src.core.args`.

Prefer :pymod:`infra_monitoring.core.args`.
"""

from __future__ import annotations

import sys as _sys

from infra_monitoring.core import args as _new_module

_sys.modules[__name__] = _new_module
