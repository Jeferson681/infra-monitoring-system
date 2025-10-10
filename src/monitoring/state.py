"""System State Manager.

# 0. Module purpose
# Este módulo gere o estado do sistema: coleta resultados de avaliação e
# produz snapshots usados pelo emissor central (core._emit_snapshot).
# 1. Imports/Constants
# 2. Classe SystemState e helpers
"""

from __future__ import annotations
import time
from datetime import datetime, timezone
from threading import Thread
from typing import Any, Optional

from config.settings import load_settings

# Estados possíveis
STATE_STABLE = "stable"
STATE_WARNING = "warning"
STATE_CRITICAL = "critical"
STATE_POST_TREATMENT = "post_treatment"


class SystemState:
    """Gerencia o estado do sistema e constrói snapshots para auditoria."""

    def __init__(
        self,
        thresholds: dict[str, Any],
        *,
        critical_duration: int | None = None,
        post_treatment_wait_seconds: int = 10,
    ):
        """Inicializa o gerenciador com thresholds e políticas de tratamento."""
        self.thresholds = thresholds
        # load settings to obtain treatment policies if available
        try:
            cfg = load_settings() or {}
            policies = cfg.get("treatment_policies", {}) or {}
        except (OSError, ValueError):
            # fallback: não conseguir ler settings -> usar políticas padrão
            policies = {}

        # sustained critical seconds (how long in critical before activating treatments)
        if critical_duration is None:
            self.sustained_crit_seconds = int(policies.get("sustained_crit_seconds", 5 * 60))
        else:
            self.sustained_crit_seconds = int(critical_duration)

        # wait time after treatments to recollect metrics (allow metrics to settle)
        self.post_treatment_wait_seconds = int(post_treatment_wait_seconds)
        # Snapshots principais
        self.current_snapshot: Optional[dict[str, Any]] = None
        self.post_treatment_snapshot: Optional[dict[str, Any]] = None

        # Controle interno (booleans em vez de dicts)
        self.is_critical_active = False
        self.treatment_active = False
        self.critical_start_time = 0.0
        # last_state kept for compatibility (can be removed later)
        self.last_state = STATE_STABLE

    # ================================================================
    # Avaliação principal
    # ================================================================

    def evaluate_metrics(self, metrics: dict[str, Any]) -> str:
        # Função principal: avalia métricas e atualiza snapshots
        """Avalia métricas e atualiza snapshots; retorna o estado resultante."""
        state = self._evaluate_against_thresholds(metrics)
        self._update_snapshots(state, metrics)
        return state

    def _evaluate_against_thresholds(self, metrics: dict[str, Any]) -> str:
        # Helper auxiliar: compara métricas com thresholds
        """Compara métricas com thresholds e determina o estado (stable/warning/critical)."""
        for name, value in metrics.items():
            limits = self.thresholds.get(name, {}) or {}
            warn = limits.get("warning")
            # aceitar 'critic' (settings default) ou 'critical' por compatibilidade
            crit = limits.get("critic") if "critic" in limits else limits.get("critical")

            try:
                if crit is not None and value is not None and value >= crit:
                    return STATE_CRITICAL
                if warn is not None and value is not None and value >= warn:
                    return STATE_WARNING
            except TypeError:
                # valor não comparável (None ou tipo inesperado) — ignorar
                continue
        return STATE_STABLE

    # ================================================================
    # Construção e controle de snapshots
    # ================================================================

    # Helper principal: atualiza snapshot corrente e agenda pós-tratamento
    def _update_snapshots(self, state: str, metrics: dict[str, Any]):
        """Atualiza o snapshot corrente e agenda pós-tratamento se necessário."""
        now = time.time()
        self.current_snapshot = self._build_snapshot(state, metrics)

        if state == STATE_CRITICAL:
            # Primeira detecção crítica
            if not self.is_critical_active:
                self.is_critical_active = True
                self.critical_start_time = now

            # Após X segundos críticos → ativa tratamento
            elif (now - self.critical_start_time) >= self.sustained_crit_seconds and not self.treatment_active:
                self._activate_treatment(metrics)

        else:
            # Reset completo quando sai do crítico
            self.is_critical_active = False
            self.treatment_active = False
            self.post_treatment_snapshot = None

        self.last_state = state

    # Helper auxiliar: constrói snapshot padrão
    def _build_snapshot(self, state: str, metrics: dict[str, Any]) -> dict[str, Any]:
        """Cria snapshot padrão com timestamp e métricas."""
        return {"state": state, "timestamp": datetime.now(timezone.utc).isoformat(), "metrics": metrics}

    # Helper auxiliar: calcula alerts a partir de métricas (reduz complexidade do worker)
    def _compute_alerts(self, metrics: dict[str, Any]) -> list[dict[str, Any]]:
        """Retorna lista de alerts (name, value, level) para as métricas fornecidas."""
        alerts: list[dict[str, Any]] = []
        try:
            for name, limits in (self.thresholds or {}).items():
                val = metrics.get(name) if isinstance(metrics, dict) else None
                if val is None:
                    continue
                alert = self._classify_metric(name, limits, val)
                if alert:
                    alerts.append(alert)
        except (TypeError, KeyError, ValueError):
            return []
        return alerts

    def _classify_metric(self, name: str, limits: dict[str, Any], val: Any) -> Optional[dict[str, Any]]:
        """Classifica uma métrica segundo thresholds e devolve alert dict ou None.

        Mantém o mesmo comportamento e captura TypeError localmente.
        """
        crit = limits.get("critic") if "critic" in limits else limits.get("critical")
        warn = limits.get("warning")
        try:
            if crit is not None and val >= crit:
                return {"name": name, "value": val, "level": STATE_CRITICAL}
            if warn is not None and val >= warn:
                return {"name": name, "value": val, "level": STATE_WARNING}
        except TypeError:
            return None
        return None

    # Helper principal: inicia execução de pós-tratamento em background
    def _activate_treatment(self, metrics: dict[str, Any]):
        """Inicia thread que recolhe métricas após aplicação de tratamentos."""
        if self.treatment_active:
            return
        self.treatment_active = True

        def _worker(metrics_snapshot: dict[str, Any]):
            try:
                time.sleep(self.post_treatment_wait_seconds)
                from monitoring.metrics import collect_metrics as _collect  # type: ignore

                metrics_after = self._safe_collect(_collect)
            except (InterruptedError, RuntimeError):
                self.treatment_active = False
                return

            alerts_after = self._compute_alerts(metrics_after)

            self.post_treatment_snapshot = {
                "state": STATE_POST_TREATMENT,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": metrics_after,
                "alerts": alerts_after,
            }

            self.treatment_active = False

        thr = Thread(target=_worker, args=(metrics,), daemon=True)
        thr.start()

    def _safe_collect(self, collect_fn) -> dict[str, Any]:
        """Executa a função de coleta protegida por tratamento de exceções.

        Mantém o comportamento original: em caso de falha retorna dict vazio.
        """
        try:
            return collect_fn()
        except (OSError, RuntimeError, ValueError, TypeError):
            return {}

    # ================================================================
    # Emissão e escrita de logs
    # ================================================================

    # emit_snapshot moved to core._emit_snapshot to centralize formatting/emission

    # write_log removed: emission centralized in core._emit_snapshot

    # ================================================================
    # Utilitários e debug
    # ================================================================

    # Utilitário: representação legível para debug
    def normalize_for_display(self) -> dict[str, Any]:
        """Retorna representação legível do estado atual."""
        output = {"current": self.current_snapshot}
        if self.treatment_active and self.post_treatment_snapshot:
            output["post_treatment"] = self.post_treatment_snapshot
        return output

    # Utilitário de teste: reinicia estado interno
    def reset(self):
        """Reinicia todo o estado interno para testes ou reuso."""
        self.current_snapshot = None
        self.post_treatment_snapshot = None
        self.is_critical_active = False
        self.treatment_active = False
        self.critical_start_time = 0.0
        self.last_state = STATE_STABLE
