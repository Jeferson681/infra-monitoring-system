"""Pacote exporter: integrações com sistemas de exportação de métricas.

Fornece integração básica com Prometheus / sistemas de scraping.

Oferece re-exports para manter compatibilidade com importações antigas
como ``from src.exporter import start_exporter``.
"""

from .prometheus import start_exporter, expose_metric  # re-export

__all__ = ["start_exporter", "expose_metric"]
