"""Gerenciamento do estado do sistema e orquestração de alertas.

Docstrings e comentários em português.

Este módulo contém um fluxo mínimo (stub) que integra:
- coleta de métricas (via monitoring.metrics.collect_metrics)
- limites/thresholds (via config.settings.get_thresholds)
- avaliação simples de estado (ESTAVEL, ALERTA, CRITIC)

O objetivo é fornecer um esqueleto seguro e não duplicado para futuros
incrementos.
"""

from __future__ import annotations

from monitoring.metrics import collect_metrics
from config.settings import (
    get_valid_thresholds,
    STATE_STABLE,
    STATE_ALERT,
    STATE_CRITIC,
)


class SystemState:
    """Orquestra o estado atual das métricas e alertas.

    Implementação mínima:
    - armazena alertas ativos em um dicionário
    - compara métricas com thresholds (alert/critic)
    - determina o estado global: 'ESTAVEL', 'ALERTA', ou 'CRITIC'
    """

    def __init__(self) -> None:
        """Inicializa o estado interno.

        Mantemos um dicionário simples de alertas e o último estado calculado.
        """
        # nome -> detalhes do alerta
        self.active_alerts: dict[str, dict] = {}
        self.last_state: str = STATE_STABLE

    def evaluate_metrics(self, metrics: dict | None = None) -> str:
        """Coleta (se necessário) e avalia métricas retornando o estado.

        Se `metrics` for None, chama `collect_metrics()` internamente.
        Retorna uma das strings: 'ESTAVEL', 'ALERTA', 'CRITIC'.
        """
        if metrics is None:
            metrics = collect_metrics()

        thresholds = get_valid_thresholds()

        overall = STATE_STABLE

        # Regras simples: se algum métrica atingir CRITIC -> CRITIC;
        # caso contrário, se alguma atingir ALERT -> ALERTA; senão ESTAVEL.
        for name, limits in thresholds.items():
            value = metrics.get(name)
            if value is None:
                # métrica indisponível: ignorar na avaliação
                continue

            critic = limits.get("critic")
            alert = limits.get("alert")

            if critic is not None and value >= critic:
                self.register_alert(name, {"value": value, "level": STATE_CRITIC})
                overall = STATE_CRITIC
                # estado crítico tem precedência absoluta
                break

            if alert is not None and value >= alert:
                # marque alerta, mas continue procurando critic
                self.register_alert(name, {"value": value, "level": STATE_ALERT})
                if overall != STATE_CRITIC:
                    overall = STATE_ALERT
            else:
                # limpa alerta se valor voltou ao normal
                self.clear_alert(name)

        self.last_state = overall
        return overall

    def register_alert(self, name: str, details: dict) -> None:
        """Registra um alerta simples (substitui se já existir)."""
        self.active_alerts[name] = details

    def clear_alert(self, name: str) -> None:
        """Remove um alerta se estiver presente."""
        if name in self.active_alerts:
            self.active_alerts.pop(name)

    def get_active_alerts(self) -> list[dict]:
        """Retorna a lista de alertas ativos como dicionários."""
        return [{"name": k, **v} for k, v in self.active_alerts.items()]

    def snapshot(self) -> dict:
        """Retorna um snapshot serializável do estado atual."""
        return {"state": self.last_state, "alerts": dict(self.active_alerts)}
