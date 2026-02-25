"""Compatibility shim for :pymod:`src.core.emitter`.

Prefer :pymod:`infra_monitoring.core.emitter`.
"""

from __future__ import annotations

import sys as _sys

from infra_monitoring.core import emitter as _new_module

_sys.modules[__name__] = _new_module
