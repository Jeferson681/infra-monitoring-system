"""Módulo de integração com Promtail para envio de logs ao Loki via HTTP.

Funções principais:
- send_log_to_loki: envia um log para o endpoint do Loki
- configure_promtail: configura parâmetros de envio (endpoint, labels, etc)

Uso:
- Importe e utilize send_log_to_loki para enviar logs formatados
- Configure via variáveis de ambiente ou argumentos.

Nota: Não exporta métricas do sistema; apenas o encaminhamento de logs é realizado aqui.
"""

import os
import json
import requests  # type: ignore[import-untyped]

LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100/api/prom/push")
LOKI_LABELS = os.getenv("LOKI_LABELS", "job=monitoring")


def send_log_to_loki(message, labels=None, timestamp=None):
    """Envia uma mensagem de log para o Loki via Promtail HTTP API.

    - message: string do log
    - labels: string no formato 'key=value,key2=value2' (opcional)
    - timestamp: epoch em nanos (opcional, default: agora).
    """
    import time

    if timestamp is None:
        timestamp = str(int(time.time() * 1e9))
    lbl = labels if labels else LOKI_LABELS
    # Monta payload no formato esperado pelo Loki
    payload = {"streams": [{"labels": f"{{{lbl}}}", "entries": [{"ts": timestamp, "line": message}]}]}
    try:
        resp = requests.post(
            LOKI_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(f"Falha ao enviar log para Loki: {exc}")
        return False
