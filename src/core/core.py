"""Loop principal e orquestração da aplicação.

Docstrings e comentários em português conforme o padrão do projeto.
"""

import logging

from system.state import SystemState


def main_loop() -> None:
    """Executa um ciclo mínimo do monitoramento (stub).

    - instancia SystemState
    - avalia métricas uma vez
    - imprime o snapshot resultante
    """
    state = SystemState()
    result = state.evaluate_metrics()
    snapshot = state.snapshot()
    # saída mínima para observabilidade do stub
    logging.info("Estado calculado: %s", result)
    logging.debug("Snapshot: %s", snapshot)


def shutdown() -> None:
    """Tarefas mínimas de encerramento (stub)."""
    pass
