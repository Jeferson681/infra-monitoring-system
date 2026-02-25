"""Compatibility shim for :pymod:`src.system.treatments`.

Prefer :pymod:`infra_monitoring.infra.system.treatments`.
"""

from __future__ import annotations

import sys as _sys

from infra_monitoring.infra.system import treatments as _new_module

_sys.modules[__name__] = _new_module
