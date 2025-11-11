"""Formatação de métricas para exibição humana.

Normaliza métricas brutas e gera resumos curtos e detalhados para console.
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# ========================
# 0. Função principal de normalização (API pública)
# ========================


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


# ========================
# 1. Resumos (summaries) — construção de summaries curtos/detalhados
# ========================


# Auxilia: normalize_for_display — constrói resumo curto (-v)
def _build_short_from_metrics(metrics: Dict[str, Any]) -> str:
    """Gere um resumo curto das métricas principais.

    Inclui CPU, RAM, Ping e Disco quando disponíveis. Retorna 'Sem dados' quando
    nada estiver disponível.
    """
    cpu = metrics.get("cpu_percent")
    mem_percent = metrics.get("memory_percent")
    disk_percent = metrics.get("disk_percent")
    ping = metrics.get("ping_ms")
    parts: list[str] = []
    if cpu is not None:
        # include optional frequency (GHz) when available; show GHz before percent
        cpu_freq = metrics.get("cpu_freq_ghz")
        if cpu_freq is not None:
            try:
                cpu_freq_f = float(cpu_freq)
                parts.append(f"CPU {cpu_freq_f:.1f}GHz • {int(round(cpu))}%")
            except Exception:
                parts.append(f"CPU {int(round(cpu))}%")
        else:
            parts.append(f"CPU {int(round(cpu))}%")
    if mem_percent is not None:
        parts.append(f"RAM {int(round(mem_percent))}%")
    if ping is not None:
        parts.append(f"Ping {int(round(ping))} ms")
    if disk_percent is not None:
        parts.append(f"Disco {int(round(disk_percent))}%")
    return " | ".join(parts) if parts else "Sem dados"


# Auxilia: normalize_for_display — constrói linhas detalhadas (-vv)
def _build_long_from_metrics(metrics: Dict[str, Any]) -> list[str]:
    r"""Gere as linhas detalhadas das métricas para exibição completa.

    Mostra CPU, RAM, Disco, Ping, Latência, Temperatura, tráfego e timestamp.
    Retorna uma lista de strings pronta para ser juntada com '\n'.
    """
    cpu = metrics.get("cpu_percent")
    mem_used = metrics.get("memory_used_bytes")
    mem_total = metrics.get("memory_total_bytes")
    disk_used = metrics.get("disk_used_bytes")
    disk_total = metrics.get("disk_total_bytes")
    ping = metrics.get("ping_ms")
    latency = metrics.get("latency_ms")
    long_lines: list[str] = []

    # CPU line: include frequency if available (GHz before percent)
    if cpu is not None:
        cpu_freq = metrics.get("cpu_freq_ghz")
        if cpu_freq is not None:
            try:
                cpu_freq_f = float(cpu_freq)
                long_lines.append(f"CPU: {cpu_freq_f:.1f}GHz • {int(round(cpu))}%")
            except Exception:
                long_lines.append(f"CPU: {int(round(cpu))}%")
        else:
            long_lines.append(f"CPU: {int(round(cpu))}%")
    else:
        long_lines.append("CPU: Indisponivel")
    mem_line = _fmt_bytes_gb(mem_used, mem_total)
    long_lines.append(f"RAM: {mem_line}")
    disk_line = _fmt_bytes_gb(disk_used, disk_total)
    long_lines.append(f"Disco: {disk_line}")
    long_lines.append(f"Ping: {ping:.1f} ms" if ping is not None else "Ping: Indisponivel")

    if latency is not None:
        # Sempre exibir em ms para evitar conversão para segundos que pode
        # mascarar que o valor é um timeout/estimativa (ex.: 10000 ms -> 10.0 s).
        long_lines.append(f"Latência: {latency:.1f} ms")
    else:
        long_lines.append("Latência: Indisponivel")

    temp = metrics.get("temperature_celsius")
    long_lines.append(f"Temperatura: {temp} C" if temp is not None else "Temperatura: Indisponivel")

    bytes_sent = metrics.get("bytes_sent")
    bytes_recv = metrics.get("bytes_recv")
    long_lines.append(f"Bytes enviados: {_fmt_bytes_human(bytes_sent)}")
    long_lines.append(f"Bytes recebidos: {_fmt_bytes_human(bytes_recv)}")

    # Append timestamp line using helper to keep complexity low
    long_lines.append(_format_timestamp_line(metrics.get("timestamp")))

    return long_lines


def _format_timestamp_line(ts_val) -> str:
    """Formatar o campo timestamp para uma linha legível.

    Retorna 'Data/hora: Indisponivel' quando não houver timestamp, ou a
    representação formatada quando possível. Em caso de parse inválido,
    retorna a representação crua.
    """
    if ts_val is None:
        return "Data/hora: Indisponivel"
    try:
        # Delegate parsing to centralized time helper which accepts multiple formats
        from ..system.time_helpers import _parse_epoch_from_value  # type: ignore
        import datetime

        parsed = _parse_epoch_from_value(ts_val)
        if parsed is None:
            # fallback to raw representation when unable to parse
            return f"Data/hora: {ts_val}"
        dt = datetime.datetime.fromtimestamp(float(parsed), tz=datetime.timezone.utc)
        return f"Data/hora: {dt.strftime('%Y-%m-%d %H:%M:%S')}"
    except Exception as exc:
        logger.debug("timestamp inválido ao formatar Data/hora: %s", exc, exc_info=True)
        return f"Data/hora: {ts_val}"


# ========================
# 2. Helpers de formatação (funções auxiliares do módulo)
# ========================


# Auxilia: _build_long_from_metrics — converte bytes para GB/percentual
def _fmt_bytes_gb(used: int | None, total: int | None) -> str:
    """Formata o uso de bytes em GB e mostra o percentual.

    Retorna 'Indisponivel' quando os dados forem insuficientes.
    """
    if used is None or total is None or total == 0:
        return "Indisponivel"
    try:
        used_gb = used / (1024**3)
        total_gb = total / (1024**3)
        percent = int(round((used / total) * 100))
        return f"{used_gb:.1f} / {total_gb:.0f} GB • {percent}%"
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        logger = logging.getLogger(__name__)
        logger.debug("erro ao formatar bytes para GB: %s", exc, exc_info=True)
        return "Indisponivel"


# Auxilia: _build_long_from_metrics — formata tráfego em MB/GB
def _fmt_bytes_human(n: int | None) -> str:
    """Formata bytes em MB/GB para legibilidade humana.

    Retorna 'Indisponivel' quando o valor for None ou inválido.
    """
    if n is None:
        return "Indisponivel"
    try:
        mb = n / (1024**2)
        gb = n / (1024**3)
        if gb >= 1.0:
            # Use two decimal places to match pre-existing expectations/tests
            return f"{gb:.2f} GB"
        # MB values also formatted with two decimals for consistency
        return f"{mb:.2f} MB"
    except (TypeError, ValueError) as exc:
        logger = logging.getLogger(__name__)
        logger.debug("erro ao formatar bytes humanamente: %s", exc, exc_info=True)
        return "Indisponivel"


def format_duration(seconds: float) -> str:
    """Retorna a duração formatada como H:MM:SS.

    Formata a duração em segundos para a representação H:MM:SS.
    Retorna '0:00:00' em caso de erro de parsing.
    """
    try:
        secs = int(round(float(seconds)))
    except Exception:
        return "0:00:00"
    import datetime

    return str(datetime.timedelta(seconds=secs))


def format_used_files_lines(used: dict) -> list[str]:
    """Retorna lista formatada de linhas com arquivos usados.

    Formata o dicionário path->(min_line, max_line) em linhas legíveis para
    exibição, preservando o comportamento anterior de `averages._format_used_files_lines`.
    """
    out: list[str] = ["", "Linhas usadas:"]
    from pathlib import Path

    for k in sorted(used.keys()):
        try:
            rng = used.get(k)
        except (AttributeError, TypeError):
            continue
        if not isinstance(rng, (list, tuple)) or len(rng) < 2:
            continue
        a, b = int(rng[0]), int(rng[1])
        try:
            fname = Path(k).name
        except Exception:
            fname = str(k)
        if a == b:
            out.append(f"{fname} linha {a}")
        else:
            out.append(f"{fname} linhas {a} a {b}")
    return out


def format_snapshot_human(snapshot: dict | None, result: dict) -> str:
    """Return a human-readable message for a snapshot/result.

    This function applies the same logic previously in core._format_human_msg:
    - prefer `summary_short` when available
    - otherwise join `summary_long` when present
    - otherwise delegate to `normalize_for_display(metrics)` to build a summary
    - fallback to 'state=<state>' when nothing else is available

    Returns a single string ready to be written to logs.
    """
    # Prefer explicit short summary from the snapshot when present.
    if isinstance(snapshot, dict):
        ss = snapshot.get("summary_short")
        if ss:
            return ss

        long_lines = snapshot.get("summary_long") or []
        if isinstance(long_lines, list) and long_lines:
            return "\n".join(str(x) for x in long_lines)

        metrics = snapshot.get("metrics")
        if isinstance(metrics, dict):
            nf = normalize_for_display(metrics)
            return nf.get("summary_short") or f"state={result.get('state')}"

        return f"state={result.get('state')}"

    return f"state={result.get('state')}"
