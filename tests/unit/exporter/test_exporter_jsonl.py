import os
import tempfile
import json
from src.exporter import prometheus


def make_fake_jsonl_dir(metrics_dict):
    """Cria um diretório temporário com um arquivo JSONL de métricas do sistema."""
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, "monitoring-2025-11-08.jsonl")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(metrics_dict) + "\n")
    return temp_dir, file_path


def test_expose_system_metrics_from_jsonl_updates_gauges():
    """Testa se expose_system_metrics_from_jsonl atualiza os Gauges corretamente a partir do JSONL."""
    metrics = {"cpu_percent": 42.5, "ram_used": 1024, "disk_free": 20480, "latency_ms": 12.3}
    temp_dir, file_path = make_fake_jsonl_dir(metrics)
    prometheus._gauges.clear()
    prometheus.expose_system_metrics_from_jsonl(temp_dir)
    # Verifica se os gauges foram atualizados corretamente
    for k, v in metrics.items():
        gauge = prometheus._gauges.get(prometheus._sanitize_metric_name(f"monitoring_{k}"))
        assert gauge is not None, f"Gauge para {k} não foi criado"
        # O valor do Gauge é acessado via gauge._value.get()
        assert gauge._value.get() == v, f"Gauge {k} não foi atualizado corretamente"
    os.remove(file_path)
    os.rmdir(temp_dir)


def test_expose_system_metrics_from_jsonl_empty_dir():
    """Testa se nenhum gauge é criado quando o diretório está vazio."""
    temp_dir = tempfile.mkdtemp()
    prometheus._gauges.clear()
    prometheus.expose_system_metrics_from_jsonl(temp_dir)
    # Nenhum gauge deve ser criado
    assert prometheus._gauges == {}
    os.rmdir(temp_dir)
