import json
import os
import psutil
import time  # Necessário para uptime
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from src.exporter.promtail import send_log_to_loki

"""
Entrypoint HTTP: expõe endpoints /health e /metrics para integração com Prometheus e orquestradores.

O uso de argparse permite que o usuário defina o endereço IP (addr) e a porta (port) do servidor HTTP
via linha de comando, sem precisar alterar o código fonte. Isso garante maior flexibilidade e segurança:
o padrão é seguro (localhost), mas o usuário pode expor externamente se já configurou firewall ou rede segura.
"""


# Caminho padrão para o diretório de JSONL de métricas do sistema
SYSTEM_METRICS_JSONL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "json")

try:

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
            # Lê a última linha do JSONL de métricas do sistema
            jsonl_path = SYSTEM_METRICS_JSONL_PATH
            system_metrics = {}
            try:
                files = [f for f in os.listdir(jsonl_path) if f.startswith("monitoring-") and f.endswith(".jsonl")]
                if files:
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
                    system_metrics = json.loads(last_json)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).exception("Falha ao ler métricas do JSONL: %s", exc)
            # Coleta métricas do processo em tempo real
            proc = psutil.Process()
            process_metrics = {
                "process_cpu_percent": proc.cpu_percent(interval=0.0),
                "process_memory_percent": proc.memory_percent(),
                "process_memory_rss_bytes": getattr(proc.memory_info(), "rss", 0),
                "process_uptime_seconds": float(max(0, (time.time() - proc.create_time()))),
                "process_num_threads": proc.num_threads(),
            }
            num_fds_fn = getattr(proc, "num_fds", None)
            if callable(num_fds_fn):
                try:
                    fds = num_fds_fn()
                    if isinstance(fds, int):
                        process_metrics["process_num_fds"] = fds
                except Exception as exc:
                    import logging

                    logging.getLogger(__name__).debug(
                        "Falha ao obter número de descritores de arquivos: %s", exc, exc_info=True
                    )
            status = {
                "status": "ok",
                "system": system_metrics,
                "process": process_metrics,
            }
            self.wfile.write(json.dumps(status).encode("utf-8"))
        elif self.path == "/metrics":
            if PROMETHEUS_AVAILABLE:
                self.send_response(200)
                self.send_header("Content-type", "text/plain; version=0.0.4; charset=utf-8")
                self.end_headers()
                # Lê a última linha do JSONL para métricas do sistema
                jsonl_path = SYSTEM_METRICS_JSONL_PATH
                system_metrics = {}
                try:
                    files = [f for f in os.listdir(jsonl_path) if f.startswith("monitoring-") and f.endswith(".jsonl")]
                    if files:
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
                            system_metrics = json.loads(last_json)
                except Exception as exc:
                    import logging

                    logging.getLogger(__name__).exception("Falha ao ler métricas do JSONL: %s", exc)
                # Coleta métricas do processo em tempo real
                proc = psutil.Process()
                process_metrics = {
                    "cpu_percent": proc.cpu_percent(interval=0.0),
                    "memory_percent": proc.memory_percent(),
                    "memory_rss_bytes": getattr(proc.memory_info(), "rss", 0),
                    "uptime_seconds": float(max(0, (time.time() - proc.create_time()))),
                    "num_threads": proc.num_threads(),
                }
                num_fds_fn = getattr(proc, "num_fds", None)
                if callable(num_fds_fn):
                    try:
                        fds = num_fds_fn()
                        if isinstance(fds, int):
                            process_metrics["num_fds"] = fds
                    except Exception as exc:
                        import logging

                        logging.getLogger(__name__).debug(
                            "Falha ao obter número de descritores de arquivos: %s", exc, exc_info=True
                        )
                # Formata para Prometheus exposition format
                lines = []
                # Métricas do sistema
                for k, v in system_metrics.items():
                    if isinstance(v, (int, float)):
                        lines.append(f"monitoring_{k} {v}")
                # Métricas do processo
                for k, v in process_metrics.items():
                    if isinstance(v, (int, float)):
                        lines.append(f"process_{k} {v}")
                output = "\n".join(lines).encode("utf-8")
                self.wfile.write(output)
            else:
                self.send_response(503)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Silencia logs de requisições HTTP no console."""
        pass


def run_http_server(addr="localhost", port=8000):
    """Inicia o servidor HTTP para expor métricas."""
    # Cria diretório de logs se não existir
    os.makedirs(os.path.dirname(__file__), exist_ok=True)
    try:
        server = HTTPServer((addr, port), HealthHandler)
        print(f"[HTTP] Servindo em http://{addr}:{port} (/health, /metrics)")
        server.serve_forever()
    except Exception as e:
        print(f"[HTTP] Erro ao iniciar servidor: {e}")


def run_promtail_worker():
    """Worker simples que envia logs de heartbeat para Loki a cada 10 segundos."""
    import logging

    while True:
        msg = f"promtail heartbeat: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        ok = send_log_to_loki(msg)
        if not ok:
            logging.getLogger(__name__).warning("Falha ao enviar heartbeat para Loki")
        time.sleep(10)


if __name__ == "__main__":
    port = int(os.getenv("MONITORING_HTTP_PORT", "8000"))
    # Inicia Promtail/Loki em thread separada
    promtail_thread = threading.Thread(target=run_promtail_worker, daemon=True)
    promtail_thread.start()
    # Inicia servidor HTTP (Prometheus)
    run_http_server(port=port)
