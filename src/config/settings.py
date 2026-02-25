"""Compatibility shim for :pymod:`src.config.settings`.

Prefer :pymod:`infra_monitoring.infra.config.settings`.
"""

from __future__ import annotations

import sys as _sys

from infra_monitoring.infra.config import settings as _new_module

_sys.modules[__name__] = _new_module
