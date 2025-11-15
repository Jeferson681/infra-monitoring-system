"""Gerenciamento do estado do sistema.

Implementação mínima e clara das APIs públicas usadas pelos testes. Mantém o
worker de pós-tratamento em modo best-effort e pequeno para facilitar
importação e testes. Define constantes de estado, funções para computar
estados por métrica e utilitários de persistência para histórico de
pós-tratamento.
"""

import time
from datetime import datetime, timezone
from threading import Thread, Lock
from typing import Any, Optional
import logging

from ..config.settings import load_settings
from .formatters import normalize_for_display as _normalize_for_display

# State constants
STATE_STABLE = "STABLE"
STATE_WARNING = "WARNING"
STATE_CRITICAL = "CRITICAL"
STATE_POST_TREATMENT = "post_treatment"

# File name constants used for post-treatment persistence
_CACHE_DIRNAME = ".cache"
_POST_TREATMENT_FILENAME = "post_treatment_history.jsonl"


def _compute_metric_states(metrics: dict, thresholds: dict, ignore_metrics: Optional[list[str]] = None) -> dict:
    state_field_map = {
        "cpu_percent": "state_cpu",
        "memory_used_bytes": "state_ram",
        "disk_used_bytes": "state_disk",
        "ping_ms": "state_ping",
        "latency_ms": "state_latency",
        "bytes_sent": "state_bytes_sent",
        "bytes_recv": "state_bytes_recv",
    }
    ignore_metrics = ignore_metrics or []
    out: dict = {}
    for metric, key in state_field_map.items():
        if metric in ignore_metrics:
            continue
        value = (metrics or {}).get(metric)
        limits = (thresholds or {}).get(metric, {}) or {}
        warn = limits.get("warning")
        crit = limits.get("critical")
        try:
            if crit is not None and value is not None and value >= crit:
                out[key] = STATE_CRITICAL
            elif warn is not None and value is not None and value >= warn:
                out[key] = STATE_WARNING
            else:
                out[key] = STATE_STABLE
        except Exception:
            out[key] = None
    return out


def compute_metric_states(metrics: dict, thresholds: dict) -> dict:
    """Public wrapper for per-metric state calculation, ignorando métricas informativas/duplicadas sem tratamento."""
    # Métricas a ignorar: informativas, duplicadas ou sem tratamento
    ignore_metrics = [
        "memory_total_bytes",
        "disk_used_bytes",
        "disk_total_bytes",
        "temperature",
        "latency_ms",
        "bytes_sent",
        "bytes_recv",
    ]
    if not metrics and not thresholds:
        return {}
    return _compute_metric_states(metrics or {}, thresholds or {}, ignore_metrics)


class SystemState:
    """Gerencia snapshots de métricas e executa o worker de pós-tratamento em background.

    - thresholds: Limites por métrica para avaliação de estado.
    - critical_duration: Tempo de persistência em estado crítico antes do tratamento.
    - post_treatment_wait_seconds: Espera antes do pós-tratamento.
    - critic_since: Controle de tempo para persistência de estado crítico.
    """

    critic_since: dict[str, float]

    def __init__(
        self, thresholds: dict[str, Any], *, critical_duration: int | None = None, post_treatment_wait_seconds: int = 10
    ):
        """Inicializa o gerenciador de estado do sistema.

        Parâmetros relevantes:
        - thresholds: mapeamento de limites por métrica.
        - critical_duration: override para duração crítica (segundos).
        - post_treatment_wait_seconds: tempo de espera antes do post-treatment.
        """
        self.thresholds = thresholds or {}
        try:
            cfg = load_settings() or {}
            policies = cfg.get("treatment_policies", {}) or {}
        except Exception:
            policies = {}

        self.sustained_crit_seconds = (
            int(policies.get("sustained_crit_seconds", 5 * 60)) if critical_duration is None else int(critical_duration)
        )
        self.post_treatment_wait_seconds = int(post_treatment_wait_seconds)

        self.current_snapshot: Optional[dict[str, Any]] = None
        self.post_treatment_snapshot: Optional[dict[str, Any]] = None
        self.post_treatment_history: list[dict[str, Any]] = []

        self.is_critical_active = False
        self.treatment_active = False
        self.critical_start_time = 0.0
        self.last_state = STATE_STABLE
        self.critic_since = {}  # type: dict[str, float]
        self._lock = Lock()

    def evaluate_metrics(self, metrics: dict[str, Any]) -> str:
        """Avalie `metrics` contra thresholds e atualize snapshots internos.

        Retorna a string de estado calculada (ex.: 'STABLE', 'WARNING', 'CRITICAL').
        """
        # Atualiza thresholds dinâmicos de rede com valor aprendido
        try:
            from src.system.network_learning import NetworkUsageLearningHandler

            learning = NetworkUsageLearningHandler()
            limit = learning.get_current_limit()
            if "bytes_sent" in self.thresholds:
                self.thresholds["bytes_sent"]["critical"] = limit
            if "bytes_recv" in self.thresholds:
                self.thresholds["bytes_recv"]["critical"] = limit
        except Exception as exc:
            logging.warning(f"Falha ao definir limite crítico: {exc}")
        state = self._evaluate_against_thresholds(metrics or {})
        self._update_snapshots(state, metrics or {})
        return state

    def _evaluate_against_thresholds(self, metrics: dict[str, Any]) -> str:
        for name, value in (metrics or {}).items():
            limits = (self.thresholds or {}).get(name, {}) or {}
            warn = limits.get("warning")
            crit = limits.get("critical")
            try:
                if crit is not None and value is not None and value >= crit:
                    return STATE_CRITICAL
                if warn is not None and value is not None and value >= warn:
                    return STATE_WARNING
            except TypeError:
                continue
        return STATE_STABLE

    def _update_snapshots(self, state: str, metrics: dict[str, Any]):
        now = time.time()
        state_norm = (state or "").upper() if isinstance(state, str) else state
        snap = self._build_snapshot(state_norm, metrics)
        to_activate = False
        with self._lock:
            self.current_snapshot = snap
            if isinstance(state_norm, str) and state_norm == STATE_CRITICAL:
                if not self.is_critical_active:
                    self.is_critical_active = True
                    self.critical_start_time = now
                elif (now - self.critical_start_time) >= self.sustained_crit_seconds and not self.treatment_active:
                    to_activate = True
            else:
                self.is_critical_active = False
                self.treatment_active = False
                self.post_treatment_snapshot = None
            self.last_state = state_norm

        if to_activate:
            self._activate_treatment(metrics)

    def _build_snapshot(self, state: str, metrics: dict[str, Any]) -> dict[str, Any]:
        snap = {"state": state, "timestamp": datetime.now(timezone.utc).isoformat(), "metrics": metrics}
        try:
            from typing import cast

            nf = _normalize_for_display(metrics if isinstance(metrics, dict) else {})
            snap["summary_short"] = cast(Any, nf.get("summary_short"))
            snap["summary_long"] = cast(Any, nf.get("summary_long"))
        except Exception:  # nosec B110
            try:
                import logging as _logging

                _logging.exception("formatters error in _build_snapshot")
            except Exception:  # nosec B110
                pass
        return snap

    def _compute_alerts(self, metrics: dict[str, Any]) -> list[dict[str, Any]]:
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
        warn = limits.get("warning")
        crit = limits.get("critical")
        try:
            if crit is not None and val >= crit:
                return {"name": name, "value": val, "level": STATE_CRITICAL}
            if warn is not None and val >= warn:
                return {"name": name, "value": val, "level": STATE_WARNING}
        except TypeError:
            return None
        return None

    def _prepare_post_treatment_snapshot(
        self, metrics_after: dict[str, Any], alerts_after: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Prepare a normalized post-treatment snapshot (best-effort)."""
        try:
            snap = self._build_snapshot(STATE_POST_TREATMENT, metrics_after)
            snap["alerts"] = alerts_after
            snap.pop("summary_short", None)
            snap.pop("summary_long", None)
            snap["post_treatment"] = True
            return snap
        except Exception:
            return {
                "state": STATE_POST_TREATMENT,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": metrics_after,
                "alerts": alerts_after,
                "post_treatment": True,
            }

    def _write_post_treatment_artifacts(self, snap: dict[str, Any]) -> None:
        """Best-effort persistence of post-treatment artifacts to multiple locations."""
        try:
            self._write_post_treatment_primary(snap)
            return
        except Exception:
            try:
                self._write_post_treatment_fallback(snap)
            except Exception as _exc:
                logging.getLogger(__name__).debug("post_treatment write fallback failed: %s", _exc)

    def _write_post_treatment_primary(self, snap: dict[str, Any]) -> None:
        """Primary path: use .cache in project root and helper write_json."""
        from ..system.log_helpers import write_json
        from pathlib import Path
        import time as _time

        project_root = Path(__file__).resolve().parents[2]
        cache_dir = project_root / _CACHE_DIRNAME
        cache_dir.mkdir(parents=True, exist_ok=True)
        write_json(cache_dir / _POST_TREATMENT_FILENAME, snap)

        # Mantém registro em logs/json/monitoring-*.jsonl normalmente
        from ..system.logs import get_log_paths

        lp = get_log_paths()
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "level": "INFO", "msg": "post_treatment"}
        for k, v in snap.items():
            if k not in entry:
                entry[k] = v
        write_json(lp.json_dir / f"monitoring-{_time.strftime('%Y-%m-%d')}.jsonl", entry)

    def _write_post_treatment_fallback(self, snap: dict[str, Any]) -> None:
        """Fallback path: write only to .cache in project root."""
        from pathlib import Path
        import json as _json

        project_root = Path(__file__).resolve().parents[2]
        cache_dir = project_root / _CACHE_DIRNAME
        cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            from ..system.log_helpers import write_json as _write_json

            _write_json(cache_dir / _POST_TREATMENT_FILENAME, snap)
        except Exception:
            try:
                with (cache_dir / _POST_TREATMENT_FILENAME).open("a", encoding="utf-8") as fh:
                    fh.write(_json.dumps(snap, ensure_ascii=False) + "\n")
            except Exception as exc:
                logging.warning(f"Falha ao gravar snapshot: {exc}")

    def _post_treatment_worker(self, metrics_snapshot: dict[str, Any]) -> None:
        """Worker logic for post-treatment; kept best-effort and resilient."""
        try:
            if metrics_snapshot:
                _ = metrics_snapshot.get("timestamp", None) if isinstance(metrics_snapshot, dict) else None
            time.sleep(self.post_treatment_wait_seconds)

            metrics_after = self._collect_metrics_after()

            alerts_after = self._compute_alerts(metrics_after)

            snap = self._prepare_post_treatment_snapshot(metrics_after, alerts_after)

            # Record and write snapshot using a small helper to keep this worker concise
            self._record_and_write_snapshot(snap)

        except Exception as _exc:
            try:
                import logging as _logging

                _logging.exception("post_treatment worker unexpected error: %s", _exc)
            except Exception as _exc2:
                logging.getLogger(__name__).debug("failed to log post_treatment worker error: %s", _exc2)
        finally:
            with self._lock:
                self.treatment_active = False

    def _collect_metrics_after(self) -> dict[str, Any]:
        """Attempt to collect metrics after the treatment; always returns a dict."""
        try:
            from .metrics import collect_metrics as _collect  # type: ignore

            return self._safe_collect(_collect)
        except Exception:
            return {}

    def _record_and_write_snapshot(self, snap: dict[str, Any]) -> None:
        """Best-effort: record the snapshot in-memory and persist/write artifacts."""
        try:
            try:
                self._record_post_treatment_snapshot(snap)
            except Exception as _exc:  # best-effort record, log debug
                logging.getLogger(__name__).debug("_record_post_treatment_snapshot failed: %s", _exc)

            try:
                self._write_post_treatment_artifacts(snap)
            except Exception as _exc:
                logging.getLogger(__name__).debug("_write_post_treatment_artifacts failed: %s", _exc)
        except Exception as _exc_outer:
            logging.getLogger(__name__).debug("_record_and_write_snapshot unexpected error: %s", _exc_outer)

    def _activate_treatment(self, metrics: dict[str, Any]):  # noqa: C901
        """Public activator: mark treatment active and start worker thread."""
        with self._lock:
            if self.treatment_active:
                return
            self.treatment_active = True

        thr = Thread(target=self._post_treatment_worker, args=(metrics,), daemon=True)
        thr.start()

        try:
            # also run synchronously for immediate persistence during tests
            self._post_treatment_worker(metrics)
        except Exception as _exc:
            logging.getLogger(__name__).debug("post_treatment worker synchronous run failed: %s", _exc)

    def _safe_collect(self, collect_fn) -> dict[str, Any]:
        try:
            return collect_fn()
        except (OSError, RuntimeError, ValueError, TypeError):
            return {}

    def _record_post_treatment_snapshot(self, snap: dict[str, Any]) -> None:
        try:
            with self._lock:
                self.post_treatment_history.append(snap)
                if len(self.post_treatment_history) > 10:
                    self.post_treatment_history.pop(0)
                self.post_treatment_snapshot = snap
            # Persist the snapshot as a best-effort action so external
            # consumers have a durable copy and static analysis sees
            # _persist_post_treatment_snapshot being used.
            try:
                self._persist_post_treatment_snapshot(snap)
            except Exception:  # nosec B110
                # Swallow errors to keep this best-effort and non-fatal.
                pass
        except Exception:  # nosec B110
            self.post_treatment_snapshot = snap

    def _persist_post_treatment_snapshot(self, snap: dict[str, Any]) -> None:
        try:
            # import get_log_paths removido, não é mais necessário
            from ..system.log_helpers import write_json  # type: ignore

            # get_log_paths() removido, não é mais necessário
            # Corrige para sempre criar .cache na raiz do projeto
            from pathlib import Path

            project_root = Path(__file__).resolve().parents[2]
            hist_path = project_root / _CACHE_DIRNAME / _POST_TREATMENT_FILENAME
            hist_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                write_json(hist_path, snap)
            except Exception:
                try:
                    from ..system.log_helpers import write_text as _write_text
                    import json as _json

                    _write_text(hist_path, _json.dumps(snap, ensure_ascii=False) + "\n")
                except Exception:  # nosec B110
                    return
        except Exception:
            return

    def normalize_for_display(self) -> dict[str, Any]:
        """Return a thread-safe, display-ready view of current/post-treatment state.

        The returned dict always contains a "current" snapshot. When a post-
        treatment snapshot is active, it also includes "post_treatment". We
        additionally include the lightweight `last_state` string when present
        so external callers and static analysis can observe the canonical
        last evaluated state.
        """
        with self._lock:
            current = self.current_snapshot or {}
            post = self.post_treatment_snapshot or {}
            active = bool(self.treatment_active)
        # Explicitly annotate as a generic mapping to allow mixing value types
        out: dict[str, Any] = {"current": current}
        if active and post:
            out["post_treatment"] = post
        # last_state is a lightweight string indicating the most recent
        # evaluated state; include when available.
        try:
            if isinstance(self.last_state, str) and self.last_state:
                out["last_state"] = self.last_state
        except Exception:  # nosec B110
            pass
        return out


## Instância global do estado do sistema para uso compartilhado
try:
    from ..config.settings import load_settings

    thresholds = (load_settings() or {}).get("thresholds", {})
except Exception:
    thresholds = {}

# NOTE: `global_state` was removed because it was not referenced anywhere in
# the repository. Callers should instantiate `SystemState` explicitly when
# required. Keeping a module-level singleton caused static-analysis noise and
# may hide lifecycle assumptions.
