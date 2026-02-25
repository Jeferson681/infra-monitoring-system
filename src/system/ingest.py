"""Compatibility shim for :pymod:`src.system.ingest`.

Prefer :pymod:`infra_monitoring.infra.system.ingest`.
"""

from __future__ import annotations

import sys as _sys

from infra_monitoring.infra.system import ingest as _new_module

_sys.modules[__name__] = _new_module
