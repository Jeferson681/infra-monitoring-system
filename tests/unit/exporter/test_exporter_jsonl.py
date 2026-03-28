import json
from pathlib import Path

import pytest

from infra_monitoring.api.exporter import prometheus


def make_fake_jsonl_dir(metrics_dict, tmp_path: Path):
    """Cria um arquivo JSONL em `tmp_path` com o conteúdo fornecido."""
    file_path = tmp_path / "monitoring-2025-11-08.jsonl"
    file_path.write_text(json.dumps(metrics_dict) + "\n", encoding="utf-8")
    return str(tmp_path), str(file_path)


def test_expose_system_metrics_from_jsonl_updates_gauges(tmp_path):
    """expose_system_metrics_from_jsonl atualiza os Gauges corretamente a partir do JSONL."""
    metrics = {
        "cpu_percent": 42.5,
        "ram_used": 1024,
        "disk_free": 20480,
        "latency_ms": 12.3,
    }
    temp_dir, file_path = make_fake_jsonl_dir(metrics, tmp_path)
    prometheus._gauges.clear()
    prometheus.expose_system_metrics_from_jsonl(temp_dir)
    # Verifica se os gauges foram atualizados corretamente
    for k, v in metrics.items():
        san = prometheus._sanitize_metric_name(f"monitoring_{k}")
        gauge = prometheus._gauges.get(san)
        assert gauge is not None, f"Gauge para {k} não foi criado"
        # The gauge value may be stored in different ways depending on impl
        val = None
        if hasattr(gauge, "value"):
            val = gauge.value
        else:
            val = getattr(getattr(gauge, "_value", {}), "get", lambda: None)()
        assert isinstance(val, (int, float))
        assert float(val) == pytest.approx(float(v))


def test_expose_system_metrics_from_jsonl_empty_dir(tmp_path):
    """Nenhum gauge é criado quando o diretório está vazio."""
    prometheus._gauges.clear()
    prometheus.expose_system_metrics_from_jsonl(str(tmp_path))
    # Nenhum gauge deve ser criado
    assert prometheus._gauges == {}
