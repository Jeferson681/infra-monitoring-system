# vulture: ignore
"""Integração com Prometheus/Grafana.

Docstrings em português.
"""


def start_exporter() -> None:  # vulture: ignore
    """Start HTTP exporter for Prometheus scraping."""
    pass


# vulture: ignore
def expose_metric(name: str, value: float) -> None:  # vulture: ignore
    """Expose a single metric to the exporter registry."""
    pass
