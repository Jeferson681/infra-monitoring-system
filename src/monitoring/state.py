from typing import Callable
import time
import logging

from config.settings import (
    get_valid_thresholds,
    STATE_STABLE,
    STATE_WARNING,
    STATE_CRITIC,
)
from config.settings import load_settings
from monitoring.handlers import attempt_treatment
from monitoring.formatters import normalize_for_display
from system import treatments as treatments

logger = logging.getLogger(__name__)


def _annotate_alerts_on_lines(nf: dict, alerts: list[dict]) -> None:
    try:
        lines = nf.get("summary_long") or []
        if not isinstance(lines, list):
            return
        mapping = {a.get("name"): a for a in alerts}
        for metric_name, details in mapping.items():
            level = details.get("level")
            if not level:
                continue
            label = "WARNING" if level == STATE_WARNING else ("CRITIC" if level == STATE_CRITIC else None)
            if not label:
                continue
            if not metric_name:
                continue
            prefix_candidates = [
                metric_name.replace("_", " ").lower(),
                metric_name.lower(),
            ]
            for i, ln in enumerate(lines):
                if not isinstance(ln, str):
                    continue
                ln_l = ln.lower()
                if any(ln_l.startswith(p) for p in prefix_candidates):
                    lines[i] = f"{ln} ({label}: acima do limite)"
                    break
    except Exception:
        return


class SystemState:  # noqa: C901
    def __init__(self) -> None:  # noqa: C901
        self.active_alerts: dict[str, dict] = {}
        self.last_state: str = STATE_STABLE
        self.last_snapshot: dict | None = None
        self.last_before_critic: dict | None = None
        self.last_after_critic: dict | None = None
        self.critic_since: dict[str, float] = {}
        try:
            cfg = load_settings() or {}
            policies = cfg.get("treatment_policies", {}) or {}
        except Exception:
            policies = {}
        self.sustained_critic_seconds: int = int(policies.get("sustained_crit_seconds", 5 * 60))
        self.min_critical_alerts: int = int(policies.get("min_critical_alerts", 1))
        try:
            self.cleanup_temp_age_days: int = int(policies.get("cleanup_temp_age_days", 7))
        except Exception:
            logger.debug(
                "invalid cleanup_temp_age_days in policies, using default: %s",
                policies.get("cleanup_temp_age_days"),
                exc_info=True,
            )
            self.cleanup_temp_age_days = 7
        default_cooldowns = {
            "cleanup_temp_files": 3 * 24 * 3600,
            "check_disk_usage": 24 * 3600,
            "trim_process_working_set_windows": 60 * 60,
            "reap_zombie_processes": 60 * 60,
            "reapply_network_config": 30 * 60,
        }
        self.treatment_cooldowns: dict[str, int] = dict(default_cooldowns)
        pc = policies.get("treatment_cooldowns") or {}
        for k, v in pc.items():
            try:
                self.treatment_cooldowns[k] = int(v)
            except Exception as exc:
                logger.debug("invalid cooldown override for %s: %s", k, exc, exc_info=True)
                continue
        self.last_treatment_run: dict[str, float] = {}

        def _stable() -> dict:
            alerts = [{"name": k, **v} for k, v in self.active_alerts.items()]
            nf = normalize_for_display(getattr(self, "last_metrics", {}))
            return {"state": STATE_STABLE, "alerts": alerts, **nf}

        def _warning() -> dict:
            alerts = [{"name": k, **v} for k, v in self.active_alerts.items()]
            nf = normalize_for_display(getattr(self, "last_metrics", {}))
            single = None
            if alerts:
                single = alerts[0]["name"]
            if single:
                nf["summary_short"] = f"{self.last_state}: {nf.get('summary_short', '')} ({single})"
                nf["summary_long"] = [f"STATUS {self.last_state}:"] + nf.get("summary_long", [])
            if alerts:
                _annotate_alerts_on_lines(nf, alerts)
            return {"state": self.last_state, "alerts": alerts, **nf}

        def _before_critic() -> dict:
            alerts = [{"name": k, **v} for k, v in self.active_alerts.items()]
            nf = normalize_for_display(getattr(self, "last_metrics", {}))
            single = None
            if alerts:
                single = alerts[0]["name"]
            if single:
                nf["summary_short"] = f"{self.last_state}: {nf.get('summary_short', '')} ({single})"
                nf["summary_long"] = [f"STATUS {self.last_state}:"] + nf.get("summary_long", [])
            if alerts:
                _annotate_alerts_on_lines(nf, alerts)
            return {"state": self.last_state, "alerts": alerts, **nf}

        def _after_critic() -> dict:
            alerts = [{"name": k, **v} for k, v in self.active_alerts.items()]
            nf = normalize_for_display(getattr(self, "last_metrics", {}))
            single = None
            if alerts:
                single = alerts[0]["name"]
            if single:
                nf["summary_short"] = f"{self.last_state}: {nf.get('summary_short', '')} ({single})"
                nf["summary_long"] = [f"STATUS {self.last_state}:"] + nf.get("summary_long", [])
            if alerts:
                _annotate_alerts_on_lines(nf, alerts)
            return {"state": self.last_state, "alerts": alerts, **nf}

        self.snapshot_builders: dict[str, Callable[[], dict]] = {
            "stable": _stable,
            "warning": _warning,
            "before_critic": _before_critic,
            "after_critic": _after_critic,
        }

    def evaluate_metrics(self, metrics: dict | None = None) -> dict:  # noqa: C901
        if metrics is None:
            try:
                from monitoring.metrics import collect_metrics  # type: ignore

                metrics = collect_metrics()
            except Exception as exc:
                logger.debug("import/chamada de collect_metrics falhou: %s", exc, exc_info=True)
                metrics = {}

        try:
            self.last_metrics = dict(metrics or {})
            try:
                from monitoring.metrics import get_memory_info, get_disk_usage_info  # type: ignore

                mu, mt = get_memory_info()
                du, dt = get_disk_usage_info()
                if mu is not None and mt is not None:
                    self.last_metrics.setdefault("memory_used_bytes", mu)
                    self.last_metrics.setdefault("memory_total_bytes", mt)
                if du is not None and dt is not None:
                    self.last_metrics.setdefault("disk_used_bytes", du)
                    self.last_metrics.setdefault("disk_total_bytes", dt)
            except Exception as exc:
                logger.debug("enriquecimento de métricas falhou: %s", exc, exc_info=True)
                pass
        except Exception as exc:
            logger.debug("falha ao atribuir last_metrics: %s", exc, exc_info=True)
            self.last_metrics = metrics or {}

        thresholds = get_valid_thresholds()
        self.active_alerts = {}
        state = STATE_STABLE
        state = self._evaluate_against_thresholds(metrics, thresholds)
        self.last_state = state
        now = time.monotonic()
        for m, details in self.active_alerts.items():
            if details.get("level") == STATE_CRITIC:
                self.critic_since.setdefault(m, now)
        for k in tuple(self.critic_since.keys()):
            if k not in self.active_alerts or self.active_alerts.get(k, {}).get("level") != STATE_CRITIC:
                self.critic_since.pop(k, None)

        if state in (STATE_STABLE, STATE_WARNING):
            key = "stable" if state == STATE_STABLE else "warning"
            snap = self.snapshot_builders[key]()
            self.last_snapshot = snap
            return {"state": state, "snapshot": snap}

        before = self.snapshot_builders["before_critic"]()
        self.last_before_critic = before
        critic_count = sum(1 for d in self.active_alerts.values() if d.get("level") == STATE_CRITIC)
        if critic_count >= self.min_critical_alerts:
            for name, details in self.active_alerts.items():
                if details.get("level") != STATE_CRITIC:
                    continue
                try:
                    res = attempt_treatment(self, name, details)
                    if isinstance(res, dict):
                        import logging

                        logging.getLogger(__name__).info(
                            "tratamento executado: %s resultado=%s",
                            res.get("action"),
                            res.get("result"),
                        )
                except Exception as exc:
                    logger.debug("tentativa de tratamento gerou exceção: %s", exc, exc_info=True)
                    pass

        try:
            from monitoring.metrics import collect_metrics as _collect  # type: ignore

            metrics_after = _collect()
        except Exception:
            metrics_after = {}
        after_state = self._evaluate_against_thresholds(metrics_after, thresholds, store=False)
        self.active_alerts = self._collect_alerts(metrics_after, thresholds)
        self.last_state = after_state
        after = self.snapshot_builders["after_critic"]()
        self.last_after_critic = after
        self.last_snapshot = {"before": before, "after": after}
        return {"state": self.last_state, "before": before, "after": after}

    def _evaluate_against_thresholds(self, metrics: dict, thresholds: dict, store: bool = True) -> str:
        state = STATE_STABLE
        alerts: dict[str, dict] = {}
        for name, limits in thresholds.items():
            value = metrics.get(name)
            if value is None:
                continue
            critic = limits.get("critic")
            if critic is not None and value >= critic:
                alerts[name] = {"value": value, "level": STATE_CRITIC}
                if store:
                    self.active_alerts = alerts
                return STATE_CRITIC
            alert = limits.get("alert")
            if alert is not None and value >= alert:
                alerts[name] = {"value": value, "level": STATE_WARNING}
                state = STATE_WARNING
        if store:
            self.active_alerts = alerts
        return state

    def _collect_alerts(self, metrics: dict, thresholds: dict) -> dict:
        alerts: dict[str, dict] = {}
        for name, limits in thresholds.items():
            value = metrics.get(name)
            if value is None:
                continue
            critic = limits.get("critic")
            if critic is not None and value >= critic:
                alerts[name] = {"value": value, "level": STATE_CRITIC}
                return alerts
            alert = limits.get("alert")
            if alert is not None and value >= alert:
                alerts[name] = {"value": value, "level": STATE_WARNING}
        return alerts

    def snapshot_before_critic(self) -> dict:
        alerts = [{"name": k, **v} for k, v in self.active_alerts.items()]
        return {"state": self.last_state, "alerts": alerts}

    def snapshot_after_critic(self) -> dict:
        before = self.snapshot_before_critic()
        after = self.snapshot_before_critic()
        return {"before": before, "after": after}

    def snapshot_warning(self) -> dict:
        return self.snapshot_before_critic()

    def snapshot_stable(self) -> dict:
        alerts = [{"name": k, **v} for k, v in self.active_alerts.items()]
        return {"state": STATE_STABLE, "alerts": alerts}
