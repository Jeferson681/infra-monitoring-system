"""Entrypoint HTTP: expõe endpoints /health e /metrics para integração com Prometheus e orquestradores."""

import json
import os
import psutil
import time  # Necessário para uptime
from http.server import BaseHTTPRequestHandler, HTTPServer
from src.monitoring.metrics import collect_metrics

try:

    from src.exporter.exporter import expose_process_metrics
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler para endpoints /health e (opcionalmente) /metrics."""

    def do_GET(self):
        """Manipula requisições GET para /health, /metrics e outros endpoints.

        Retorna status do host, métricas do processo ou métricas Prometheus.
        """
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            # Coleta métricas do host
            metrics = collect_metrics()
            # Coleta métricas do processo
            proc = psutil.Process()
            process_metrics = {
                "process_cpu_percent": proc.cpu_percent(interval=0.0),
                "process_memory_percent": proc.memory_percent(),
                "process_memory_rss_bytes": getattr(proc.memory_info(), "rss", 0),
                "process_uptime_seconds": float(max(0, (time.time() - proc.create_time()))),
                "process_num_threads": proc.num_threads(),
            }
            # Só adiciona a métrica se o método existir
            num_fds_fn = getattr(proc, "num_fds", None)
            if callable(num_fds_fn):
                try:
                    fds = num_fds_fn()
                    if isinstance(fds, int):
                        process_metrics["process_num_fds"] = fds
                except Exception as exc:
                    # Pode ocorrer em plataformas sem suporte a num_fds; ignora silenciosamente
                    import logging

                    logging.getLogger(__name__).debug(
                        "Falha ao obter número de descritores de arquivos: %s", exc, exc_info=True
                    )
            status = {
                "status": "ok",
                "host": {
                    "cpu_percent": metrics.get("cpu_percent"),
                    "memory_percent": metrics.get("memory_percent"),
                    "disk_percent": metrics.get("disk_percent"),
                    "timestamp": metrics.get("timestamp"),
                },
                "process": process_metrics,
            }
            self.wfile.write(json.dumps(status).encode("utf-8"))
        elif self.path == "/metrics" and PROMETHEUS_AVAILABLE:
            # Atualiza métricas do processo antes de expor
            expose_process_metrics()
            output = generate_latest()
            self.send_response(200)
            self.send_header("Content-type", CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(output)
        elif self.path == "/metrics":
            self.send_response(501)
            self.end_headers()
            self.wfile.write(b"prometheus_client nao instalado")
        else:
            self.send_response(404)
            self.end_headers()


def run_http_server(port=8000, addr="0.0.0.0"):
    """Inicia o servidor HTTP para expor os endpoints /health e /metrics.

    Observação: O endereço padrão '0.0.0.0' expõe o serviço em todas as interfaces de rede, permitindo acesso externo.
    Para maior segurança em ambiente local, utilize '127.0.0.1' para restringir o acesso ao localhost.
    Sempre avalie a necessidade de exposição e proteja o serviço com firewall, autenticação
    ou rede segura conforme o caso.
    """
    server = HTTPServer((addr, port), HealthHandler)  # nosec
    print(f"[HTTP] Servindo em http://{addr}:{port} (/health, /metrics)")
    server.serve_forever()


if __name__ == "__main__":
    port = int(os.getenv("MONITORING_HTTP_PORT", "8000"))
    run_http_server(port=port)
