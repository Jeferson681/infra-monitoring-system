"""Integração com Prometheus/Grafana.

Docstrings em português.
"""


def start_exporter() -> None:
    """Start HTTP exporter for Prometheus scraping."""
    pass


def expose_metric(name: str, value: float) -> None:
    """Expose a single metric to the exporter registry."""
    pass
