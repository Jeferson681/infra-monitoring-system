"""Entrypoint HTTP: expõe endpoints /health e /metrics para integração com Prometheus e orquestradores."""

import json
import os
import psutil
import time  # Necessário para uptime
from http.server import BaseHTTPRequestHandler, HTTPServer
from src.monitoring.metrics import collect_metrics

try:

    from exporter.prometheus import expose_process_metrics
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class HealthHandler(BaseHTTPRequestHandler):
    """Handler HTTP para endpoints de saúde e métricas.

    Suporta `/health` (retorna um JSON com métricas de host e processo) e
    `/metrics` quando o cliente Prometheus estiver disponível.
    """

    def do_GET(self):
        """Trata requisições GET.

        Endpoints suportados:
        - /health: JSON com estado do host e métricas do processo.
        - /metrics: métricas em formato Prometheus quando disponível.
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
            # Só adiciona a métrica se o método existir (nem todas as plataformas
            # expõem num_fds). Este bloco é best-effort e não deve falhar a
            # requisição inteira se a métrica não puder ser obtida.
            num_fds_fn = getattr(proc, "num_fds", None)
            if callable(num_fds_fn):
                try:
                    fds = num_fds_fn()
                    if isinstance(fds, int):
                        process_metrics["process_num_fds"] = fds
                except Exception as exc:
                    # Possível em plataformas sem suporte; registrar em debug apenas
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


def run_http_server(port=8000, addr="0.0.0.0"):  # nosec B104
    """Inicia o servidor HTTP para expor os endpoints /health e /metrics.

    Args:
        port: Porta TCP onde o servidor irá escutar (padrão: 8000).
        addr: Endereço/host para binding (padrão: "0.0.0.0" - todas as
            interfaces). Em ambientes locais use "127.0.0.1" quando apropriado.

    Observação:
        O serviço exposto pode conter informações sensíveis do host. Proteja
        o acesso com firewall, autenticação ou redes privadas quando necessário.

    """
    server = HTTPServer((addr, port), HealthHandler)  # nosec
    print(f"[HTTP] Servindo em http://{addr}:{port} (/health, /metrics)")
    server.serve_forever()


if __name__ == "__main__":
    port = int(os.getenv("MONITORING_HTTP_PORT", "8000"))
    run_http_server(port=port)
