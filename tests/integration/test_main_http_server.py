import http.client
import threading
from http.server import HTTPServer

from infra_monitoring.api.exporter import main_http


def start_server_in_thread(addr="127.0.0.1", port=0):
    server = HTTPServer((addr, port), main_http.HealthHandler)
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()
    return server, th


def test_health_endpoint_returns_ok():
    server, th = start_server_in_thread()
    host, port = server.server_address
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request("GET", "/health")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert '"status": "ok"' in body
    finally:
        conn.close()
        server.shutdown()
        th.join(timeout=2)


def test_metrics_endpoint_returns_200_or_503():
    server, th = start_server_in_thread()
    host, port = server.server_address
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request("GET", "/metrics")
        resp = conn.getresponse()
        assert resp.status in (200, 503)
    finally:
        conn.close()
        server.shutdown()
        th.join(timeout=2)
