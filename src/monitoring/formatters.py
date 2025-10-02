"""Formatação de métricas para exibição humana.

Normaliza métricas brutas e gera resumos curtos e detalhados para console.
"""

from __future__ import annotations
from typing import Dict, Any

# ========================
# 0. Cabeçalho e padrões
# ========================


# ========================
# 1. Construção de summaries
# ========================


# Auxilia: normalize_for_display — constrói resumo curto (-v)
def _build_short_from_metrics(metrics: Dict[str, Any]) -> str:
    """Gera um resumo curto das métricas principais.

    Inclui CPU, RAM, Ping e Disco quando disponíveis.
    """
    cpu = metrics.get("cpu_percent")
    mem_percent = metrics.get("memory_percent")
    disk_percent = metrics.get("disk_percent")
    ping = metrics.get("ping_ms")
    parts: list[str] = []
    if cpu is not None:
        parts.append(f"CPU {int(round(cpu))}%")
    if mem_percent is not None:
        parts.append(f"RAM {int(round(mem_percent))}%")
    if ping is not None:
        parts.append(f"Ping {int(round(ping))} ms")
    if disk_percent is not None:
        parts.append(f"Disk {int(round(disk_percent))}%")
    return " | ".join(parts) if parts else "Sem dados"


# Auxilia: normalize_for_display — constrói linhas detalhadas (-vv)
def _build_long_from_metrics(metrics: Dict[str, Any]) -> list[str]:
    """Gera linhas detalhadas das métricas para exibição completa.

    Mostra CPU, RAM, Disco, Ping, Latência, Temperatura, tráfego e timestamp.
    """
    cpu = metrics.get("cpu_percent")
    mem_used = metrics.get("memory_used_bytes")
    mem_total = metrics.get("memory_total_bytes")
    disk_used = metrics.get("disk_used_bytes")
    disk_total = metrics.get("disk_total_bytes")
    ping = metrics.get("ping_ms")
    latency = metrics.get("latency_ms")
    long_lines: list[str] = []

    long_lines.append(f"CPU: {int(round(cpu))}%" if cpu is not None else "CPU: Indisponivel")
    mem_line = _fmt_bytes_gb(mem_used, mem_total)
    long_lines.append(f"RAM: {mem_line}")
    disk_line = _fmt_bytes_gb(disk_used, disk_total)
    long_lines.append(f"Disco: {disk_line}")
    long_lines.append(f"Ping: {ping:.1f} ms" if ping is not None else "Ping: Indisponivel")

    if latency is not None:
        # Sempre exibir em ms para evitar conversão para segundos que pode
        # mascarar que o valor é um timeout/estimativa (ex.: 10000 ms -> 10.0 s).
        long_lines.append(f"Latency: {latency:.1f} ms")
    else:
        long_lines.append("Latency: Indisponivel")

    temp = metrics.get("temperature_celsius")
    long_lines.append(f"Temperatura: {temp} C" if temp is not None else "Temperatura: Indisponivel")

    bytes_sent = metrics.get("bytes_sent")
    bytes_recv = metrics.get("bytes_recv")
    long_lines.append(f"Bytes enviados: {_fmt_bytes_human(bytes_sent)}")
    long_lines.append(f"Bytes recebidos: {_fmt_bytes_human(bytes_recv)}")

    ts = metrics.get("timestamp")
    if ts is None:
        long_lines.append("Data/hora: Indisponivel")
    else:
        try:
            import datetime

            dt = datetime.datetime.fromtimestamp(float(ts))
            # Mostrar apenas até segundos, sem milissegundos
            long_lines.append(f"Data/hora: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception:
            long_lines.append(f"Data/hora: {ts}")

    return long_lines


# ========================
# 2. Helpers de formatação (exclusivos do módulo)
# ========================


# Auxilia: _build_long_from_metrics — converte bytes para GB/percentual
def _fmt_bytes_gb(used: int | None, total: int | None) -> str:
    """Formata uso de bytes em GB e exibe percentual.

    Retorna 'Indisponivel' quando dados insuficientes.
    """
    if used is None or total is None or total == 0:
        return "Indisponivel"
    try:
        used_gb = used / (1024**3)
        total_gb = total / (1024**3)
        percent = int(round((used / total) * 100))
        return f"{used_gb:.1f} / {total_gb:.0f} GB - {percent}%"
    except Exception:
        return "Indisponivel"


# Auxilia: _build_long_from_metrics — formata tráfego em MB/GB
def _fmt_bytes_human(n: int | None) -> str:
    """Formata bytes para MB ou GB de forma legível.

    Retorna 'Indisponivel' quando o valor é None ou inválido.
    """
    if n is None:
        return "Indisponivel"
    try:
        mb = n / (1024**2)
        gb = n / (1024**3)
        if gb >= 1.0:
            return f"{gb:.1f} GB"
        return f"{mb:.1f} MB"
    except Exception:
        return "Indisponivel"


# ========================
# 3. Função principal de normalização
# ========================


# Fornece: normalize_for_display — cria summaries prontos para exibição
def normalize_for_display(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza métricas brutas em estrutura pronta para exibição.

    Retorna dict com 'summary_short', 'summary_long' e 'metrics_raw'.
    """
    summary_short = _build_short_from_metrics(metrics)
    long_lines = _build_long_from_metrics(metrics)

    return {
        "summary_short": summary_short,
        "summary_long": long_lines,
        "metrics_raw": metrics,
    }
