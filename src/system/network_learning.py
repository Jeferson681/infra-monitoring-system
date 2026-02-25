"""Compatibility shim for :pymod:`src.system.network_learning`.

Prefer :pymod:`infra_monitoring.infra.system.network_learning`.
"""

from __future__ import annotations

import sys as _sys

from infra_monitoring.infra.system import network_learning as _new_module

_sys.modules[__name__] = _new_module
