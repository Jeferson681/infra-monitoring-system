"""System package: support functions, automated treatments, and logging.

Includes system helpers, log rotation/compression and automated actions.

Provides a small set of re-exports for compatibility with older imports.
"""

from .log_helpers import build_human_line, write_text, write_json

__all__ = ["build_human_line", "write_text", "write_json"]
