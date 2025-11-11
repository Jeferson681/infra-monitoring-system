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
import requests  # type: ignore[import-untyped]

LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100/loki/api/v1/push")
LOKI_LABELS = os.getenv("LOKI_LABELS", "job=monitoring")


def _parse_labels(labels):
    """Converta rótulos em formato string 'k=v,k2=v2' ou dict para dict com valores string.

    Aceita também strings já no formato '{k="v"}' — retorna um dict {k: v}.
    """
    if labels is None:
        return {}
    if isinstance(labels, dict):
        return {str(k): str(v) for k, v in labels.items()}
    s = str(labels).strip()
    # Caso seja a forma '{k="v"}' -> remove chaves e aspas
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1].strip()
    # agora esperamos algo como k=v,k2=v2 ou k="v",...; normaliza
    parts = [p.strip() for p in s.split(",") if p.strip()]
    out = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            v = v.strip()
            # remove aspas se existirem
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            out[k.strip()] = v
    return out


def send_log_to_loki(message, labels=None, timestamp=None):
    """Envia uma mensagem de log para o Loki.

    Garante que o payload siga o formato JSON aceito pelo endpoint
    `/loki/api/v1/push`:

    {
      "streams": [
        {"stream": {"k":"v"}, "values": [["<unix_nano>", "log line"]]}
      ]
    }

    - message: string do log
    - labels: string 'k=v,k2=v2' ou dict (opcional)
    - timestamp: epoch em nanos como string/inteiro (opcional)
    """
    import time
    import logging

    url = os.getenv("LOKI_URL", LOKI_URL)

    if timestamp is None:
        timestamp = str(int(time.time() * 1e9))
    else:
        timestamp = str(timestamp)

    stream = _parse_labels(labels if labels is not None else LOKI_LABELS)

    payload = {"streams": [{"stream": stream, "values": [[timestamp, str(message)]]}]}

    logging.getLogger(__name__).debug("Loki payload: %s", payload)

    try:
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=5)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logging.getLogger(__name__).warning("Falha ao enviar log para Loki: %s", exc)
        return False
    except Exception as exc:
        logging.getLogger(__name__).warning("Erro inesperado ao enviar log para Loki: %s", exc)
        return False
