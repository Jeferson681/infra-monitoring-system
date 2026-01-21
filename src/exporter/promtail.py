"""Promtail integration: send logs to Loki via HTTP.

Provides ``send_log_to_loki`` to post log lines to a Loki-compatible HTTP
endpoint. Labels may be provided as a string or dict and are normalized for
the Loki API. The module is focused solely on log forwarding and does not
expose system metrics.
"""

import os
import requests  # type: ignore[import-untyped]

LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100/loki/api/v1/push")
LOKI_LABELS = os.getenv("LOKI_LABELS", "job=monitoring")


def _parse_labels(labels):
    """Convert labels in 'k=v,k2=v2' string form or dict into a dict of strings.

    Also accepts strings in the '{k="v"}' form — returns a {k: v} dict.
    """
    if labels is None:
        return {}
    if isinstance(labels, dict):
        return {str(k): str(v) for k, v in labels.items()}
    s = str(labels).strip()
    # If in the form '{k="v"}' -> remove braces and quotes
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1].strip()
    # now expect something like k=v,k2=v2 or k="v",...; normalize
    parts = [p.strip() for p in s.split(",") if p.strip()]
    out = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            v = v.strip()
            # remove quotes if present
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            out[k.strip()] = v
    return out


def send_log_to_loki(message, labels=None, timestamp=None):
    """Send a log message to Loki.

    Ensure the payload matches the JSON format accepted by
    `/loki/api/v1/push`.

    - `message`: log string
    - `labels`: 'k=v,k2=v2' string or dict (optional)
    - `timestamp`: epoch in nanoseconds as string/int (optional)
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
        logging.getLogger(__name__).warning("Failed to send log to Loki: %s", exc)
        return False
    except Exception as exc:
        logging.getLogger(__name__).warning("Unexpected error sending log to Loki: %s", exc)
        return False
