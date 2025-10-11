# vulture: ignore
"""Integração com Prometheus/Grafana.

Docstrings em português.
"""


def start_exporter() -> None:  # vulture: ignore
    """Inicie o servidor HTTP do exporter para Prometheus.

    Implementação de placeholder: a função existe para ser chamada pelo
    orquestrador quando o exporter estiver habilitado. Não realiza I/O por
    si mesma nesta implementação inicial.
    """
    pass


# vulture: ignore
def expose_metric(name: str, value: float) -> None:  # vulture: ignore
    """Exponha uma métrica ao registro do exporter.

    Parâmetros:
        name: nome da métrica a expor.
        value: valor numérico da métrica.
    """
    pass
