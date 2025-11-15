import json
import os
import logging
from typing import Dict, cast


def expose_system_metrics_from_jsonl(jsonl_path: str) -> None:
    """Lê a última linha do JSONL e expõe métricas do sistema como Gauges."""
    if not _HAVE_PROM:
        return
    try:
        files = [f for f in os.listdir(jsonl_path) if f.startswith("monitoring-") and f.endswith(".jsonl")]
        if not files:
            return
        files.sort(reverse=True)
        latest_file = os.path.join(jsonl_path, files[0])
        with open(latest_file, "rb") as f:
            f.seek(0, os.SEEK_END)
            pos = f.tell()
            line = b""
            while pos > 0:
                pos -= 1
                f.seek(pos)
                char = f.read(1)
                if char == b"\n" and line:
                    break
                line = char + line
            last_json = line.decode("utf-8").strip()
        if last_json:
            metrics = json.loads(last_json)
            for k, v in metrics.items():
                if isinstance(v, (int, float)):
                    expose_metric(f"monitoring_{k}", float(v), f"System metric {k} from JSONL")
    except Exception as exc:
        logger.debug("Falha ao expor métricas do sistema do JSONL: %s", exc, exc_info=True)


# prometheus_exporter.py
# Utilitários para exportação de métricas no padrão Prometheus.

# ...existing code...

"""
Utilitários para exportação de métricas no padrão Prometheus.

Exponha métricas para Prometheus como Gauges quando a biblioteca
`prometheus_client` estiver disponível. Se a biblioteca não estiver
instalada, as funções tornam-se no-ops e apenas logam advertências.
"""

logger = logging.getLogger(__name__)


# Try to import prometheus_client; fall back to no-op if unavailable
_HAVE_PROM = False
_gauges: Dict[str, object] = {}
_server_started = False


try:
    from prometheus_client import Gauge, start_http_server  # type: ignore

    _HAVE_PROM = True
except Exception:  # pragma: no cover - optional dependency
    # Falha ao importar prometheus_client: exportação Prometheus será desativada (opcional)
    _HAVE_PROM = False


def _sanitize_metric_name(name: str) -> str:
    """Sanitiza o nome da métrica para o padrão Prometheus, substituindo caracteres inválidos por underline."""
    # Prometheus metric names: [a-zA-Z_:][a-zA-Z0-9_:]*
    out = []
    for i, ch in enumerate(name):
        if i == 0:
            if ch.isalpha() or ch in ("_", ":"):
                out.append(ch)
            else:
                out.append("_")
        else:
            if ch.isalnum() or ch in ("_", ":"):
                out.append(ch)
            else:
                out.append("_")
    return "".join(out)


def start_exporter(port: int | None = None, addr: str = "127.0.0.1") -> None:
    """Inicia o servidor HTTP do Prometheus Exporter no endereço e porta informados.

    Se `prometheus_client` não estiver disponível, apenas loga e não faz nada.
    A porta pode ser definida pela variável de ambiente `MONITORING_EXPORTER_PORT` se `port` for None.
    """
    global _server_started
    if not _HAVE_PROM:
        logger.warning("prometheus_client not installed; exporter disabled")
        return

    if _server_started:
        logger.debug("prometheus exporter already started")
        return

    # Atualiza os Gauges do sistema a partir do JSONL ao iniciar o exporter
    jsonl_path = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "json")
    expose_system_metrics_from_jsonl(jsonl_path)

    if port is None:
        try:
            port = int(os.getenv("MONITORING_EXPORTER_PORT", "8000"))
        except Exception:
            # Se a conversão da porta falhar, usa valor padrão
            port = 8000

    try:
        start_http_server(port, addr)
        _server_started = True
        logger.info("Prometheus exporter iniciado em %s:%d", addr, port)
    except Exception as exc:
        logger.exception("Falha ao iniciar Prometheus exporter: %s", exc)


def expose_metric(name: str, value: float, description: str = "") -> None:
    """Expõe uma métrica numérica como Gauge do Prometheus.

    Cria o Gauge na primeira chamada e atualiza o valor nas próximas.
    Se `prometheus_client` não estiver disponível, apenas loga e retorna.
    """
    if not _HAVE_PROM:
        logger.debug("prometheus_client not available; expose_metric %s=%s ignored", name, value)
        # Garante que _gauges não é modificado
        return

    san = _sanitize_metric_name(name)
    try:
        # Garante que só adiciona ao _gauges se _HAVE_PROM for True
        if _HAVE_PROM:
            if san not in _gauges:
                g = Gauge(san, description or f"Gauge for {name}")
                _gauges[san] = g
            else:
                g = _gauges[san]
            # Cast to Gauge for type checkers and call set
            g_cast = cast(Gauge, g)
            g_cast.set(float(value))
    except Exception as exc:
        logger.debug("Falha ao expor métrica %s: %s", name, exc, exc_info=True)


def expose_process_metrics() -> None:
    """Compatibility wrapper that delegates to the canonical implementation.

    The real implementation lives in `src.exporter.prometheus`. Keep a thin
    wrapper here to preserve the public API while avoiding duplicated code.
    """
    try:
        # Import locally to avoid import-time side-effects and to keep the
        # canonical implementation in one place.
        from .prometheus import expose_process_metrics as _expose

        _expose()
    except Exception:
        # Best-effort: do not raise if prometheus_client is missing or the
        # delegated call fails.
        return
