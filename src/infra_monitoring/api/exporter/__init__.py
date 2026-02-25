"""Exporter package: integrations for exporting metrics.

Provides basic integration points for Prometheus and other scraping
systems. Re-exports common entrypoints to preserve backwards compatible
imports such as ``from infra_monitoring.api.exporter import start_exporter``.
"""

from .prometheus import start_exporter, expose_metric  # re-export

__all__ = ["start_exporter", "expose_metric"]
