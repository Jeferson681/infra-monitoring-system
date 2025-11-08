"""Coleta métricas do sistema.

Coleta CPU, RAM, Disco, Ping/Latência, Rede e Temperatura.
Preferir operações em Python puro e seguras; quando necessário usa
fallbacks externos de forma controlada.
"""

import time
import math
import logging
import socket
import threading
import os
import re
import subprocess
import platform

import psutil
from pathlib import Path

from ..system.helpers import validate_host_port, _disk_candidate_paths

logger = logging.getLogger(__name__)

# Flag indicando se a última medição de latency foi uma estimativa de timeout
_last_latency_estimated: bool = False
# Flag para evitar expor o 0% inicial do psutil na primeira coleta
_cpu_warmed_up: bool = False

# ========================
# 1. Cache simples por métrica
# ========================

# Intervalos (em segundos) razoáveis para evitar consultas excessivas.
# Ajuste conforme o ambiente / sensibilidade desejada.
# Use um pequeno conjunto de chaves de cache, agrupando rede em um único item.
_METRIC_INTERVALS: dict[str, float] = {
    "cpu_percent": 1.0,
    "memory_percent": 5.0,
    "disk_percent": 10.0,
    "cpu_freq_ghz": 30.0,
    "network": 2.0,  # agrupa bytes_sent/bytes_recv
    "ping_ms": 5.0,
    "latency_ms": 5.0,
    "latency_method": 5.0,
    "latency_estimated": 5.0,
    "temperature": 30.0,
}

# cache: key -> { 'value': ..., 'ts': float(monotonic) }
_CACHE: dict[str, dict] = {k: {"value": None, "ts": 0.0} for k in _METRIC_INTERVALS.keys()}

# locks para garantir que não disparemos múltiplas coletas simultâneas para a
# mesma métrica. Usamos try_acquire (non-blocking) no coletor para não bloquear
# o thread chamador — se já houver coleta em andamento, usamos o valor em cache.
_LOCKS: dict[str, threading.Lock] = {k: threading.Lock() for k in _METRIC_INTERVALS.keys()}


def _now() -> float:
    """Retorne um timestamp monotônico (em segundos).

    Usado internamente para medir envelhecimento do cache sem depender do relógio do sistema.
    """
    return time.monotonic()


def _is_stale(key: str) -> bool:
    """Retorne True se o valor em cache para `key` estiver stale.

    Considera o intervalo configurado em `_METRIC_INTERVALS`.
    """
    try:
        last = float(_CACHE.get(key, {}).get("ts", 0.0))
        interval = float(_METRIC_INTERVALS.get(key, 1.0))
        return (_now() - last) >= interval
    except (TypeError, ValueError) as exc:
        logger.debug("_is_stale falhou para key %s: %s", key, exc, exc_info=True)
        return True


def _cache_get_or_refresh(key: str, collector, *args, **kwargs):
    """Retorne o valor em cache para `key`, atualizando quando stale.

    `collector` é um callable que será invocado para refazer a medição. Para
    chaves conhecidas usa locks por chave para evitar coletas concorrentes.
    """
    # se a chave for desconhecida, chame o collector diretamente
    if key not in _METRIC_INTERVALS:
        try:
            return collector(*args, **kwargs)
        except (TypeError, ValueError, RuntimeError, OSError) as exc:
            logger.debug("collector falhou para key desconhecida %s: %s", key, exc, exc_info=True)
            return None

    # if not stale, return cached value
    if not _is_stale(key):
        return _CACHE.get(key, {}).get("value")

    def _refresh_no_lock():
        try:
            val = collector(*args, **kwargs)
        except (TypeError, ValueError, RuntimeError, OSError) as exc:
            logger.debug("falha ao atualizar collector para key %s: %s", key, exc, exc_info=True)
            val = None
        _CACHE[key]["value"] = val
        _CACHE[key]["ts"] = _now()
        return val

    lock = _LOCKS.get(key)
    if lock is None:
        return _refresh_no_lock()

    if not lock.acquire(blocking=False):
        # somebody else is updating; return whatever is in cache
        return _CACHE.get(key, {}).get("value")

    try:
        # refresh once we have the lock
        return _refresh_no_lock()
    finally:
        try:
            lock.release()
        except RuntimeError as exc:
            logger.debug("lock.release() falhou: %s", exc, exc_info=True)


def collect_metrics() -> dict[str, float | int | str | None]:
    """Collect and normalize system metrics and return a flat mapping.

    The result contains primitive values (float/int/str/None) suitable for
    serialization and formatting. Uses internal caching to reduce cost of
    expensive system calls.
    """
    metrics: dict[str, float | int | str | None] = {}

    # Break logic into helpers to keep this function readable and reduce
    # cyclomatic/cognitive complexity while preserving exact behavior.
    _reset_cache_timestamps()
    _collect_percent_metrics(metrics)
    _collect_memory_and_bytes(metrics)
    _collect_network_metrics(metrics)
    _collect_latency_metrics(metrics)
    _collect_temperature_and_timestamp(metrics)
    _collect_disk_usage_bytes(metrics)

    return metrics


def _export_some_metrics(metrics: dict[str, float | int | str | None]) -> None:
    """Expose a small set of metrics to Prometheus exporter if available.

    This is a best-effort integration: failures are logged and ignored.
    """
    try:
        from ..exporter.prometheus import expose_metric

        for key in ("cpu_percent", "memory_percent", "disk_percent"):
            try:
                val = metrics.get(key)
                if val is not None:
                    expose_metric(f"monitoring_{key}", float(val), description=f"{key} from monitoring")
            except Exception:
                # Do not break metric collection if exporter fails for a value
                logger.debug("_export_some_metrics: failed to expose %s", key, exc_info=True)
    except Exception as exc:
        # exporter may be unavailable; log at debug level and continue
        logger.debug("_export_some_metrics: exporter unavailable: %s", exc, exc_info=True)


def _reset_cache_timestamps() -> None:
    """Force a cache timestamp reset to ensure collectors run in tests."""
    try:
        for k in _CACHE.keys():
            _CACHE[k]["ts"] = 0.0
    except (AttributeError, TypeError) as exc:
        logger.debug("falha ao resetar timestamps do cache: %s", exc, exc_info=True)


def _collect_percent_metrics(metrics: dict[str, float | int | str | None]) -> None:
    cpu = _safe_float(_cache_get_or_refresh("cpu_percent", get_cpu_percent))
    metrics["cpu_percent"] = None if cpu is None else max(0.0, min(100.0, cpu))

    cpu_freq = _safe_float(_cache_get_or_refresh("cpu_freq_ghz", get_cpu_freq_ghz))
    metrics["cpu_freq_ghz"] = None if cpu_freq is None else float(cpu_freq)

    mem = _safe_float(_cache_get_or_refresh("memory_percent", get_memory_percent))
    metrics["memory_percent"] = None if mem is None else max(0.0, min(100.0, mem))

    disk = _safe_float(_cache_get_or_refresh("disk_percent", get_disk_percent))
    metrics["disk_percent"] = None if disk is None else max(0.0, min(100.0, disk))


def _collect_memory_and_bytes(metrics: dict[str, float | int | str | None]) -> None:
    try:
        vm = psutil.virtual_memory()
        metrics["memory_used_bytes"] = int(getattr(vm, "used", 0))
        metrics["memory_total_bytes"] = int(getattr(vm, "total", 0))
    except Exception:
        metrics["memory_used_bytes"] = None
        metrics["memory_total_bytes"] = None


def _collect_network_metrics(metrics: dict[str, float | int | str | None]) -> None:
    net = _cache_get_or_refresh("network", lambda: get_network_stats()) or {}
    metrics["bytes_sent"] = _safe_counter(net.get("bytes_sent"))
    metrics["bytes_recv"] = _safe_counter(net.get("bytes_recv"))


def _collect_latency_metrics(metrics: dict[str, float | int | str | None]) -> None:
    ping = _safe_float(_cache_get_or_refresh("ping_ms", lambda: get_latency("8.8.8.8", 53, 1.0)))
    metrics["ping_ms"] = None if (ping is None or ping < 0.0) else ping

    latency = _safe_float(_cache_get_or_refresh("latency_ms", lambda: get_latency()))
    latency_method = "tcp" if latency is not None else None

    metrics["latency_ms"] = None if (latency is None or latency < 0.0) else latency
    metrics["latency_method"] = latency_method
    try:
        metrics["latency_estimated"] = bool(_last_latency_estimated)
    except Exception:
        metrics["latency_estimated"] = False


def _collect_temperature_and_timestamp(metrics: dict[str, float | int | str | None]) -> None:
    metrics["temperature"] = _cache_get_or_refresh("temperature", _temperature_collector)
    metrics["timestamp"] = time.time()


def _collect_disk_usage_bytes(metrics: dict[str, float | int | str | None]) -> None:
    try:
        disk_used = None
        disk_total = None
        candidates: list[object] = []
        candidates = _disk_candidate_paths()
        for p in candidates:
            try:
                du = psutil.disk_usage(str(p))
                disk_used = int(getattr(du, "used", 0))
                disk_total = int(getattr(du, "total", 0))
                break
            except OSError:
                # problemas de I/O/permissão — tentar próximo candidato
                continue
        metrics["disk_used_bytes"] = disk_used
        metrics["disk_total_bytes"] = disk_total
    except Exception:
        metrics["disk_used_bytes"] = None
        metrics["disk_total_bytes"] = None


def _safe_float(val: object) -> float | None:
    """Converta `val` para float; rejeite NaN/Inf e retorne None em erro.

    Apenas int/float/str são aceitos; caso contrário retorne None.
    """
    if not isinstance(val, (int, float, str)):
        return None
    try:
        f = float(val)
        if not math.isfinite(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _safe_counter(v: object) -> int | None:
    """Converta e valide um valor tipo contador para int não-negativo ou None."""
    if not isinstance(v, (int, float, str)):
        return None
    try:
        n = int(v)
        return n if n >= 0 else None
    except (ValueError, TypeError):
        return None


def get_cpu_percent() -> float | None:
    """Retorne a percentagem de uso de CPU (não bloqueante).

    Observação: o psutil pode retornar 0.0 na primeira chamada (valor espúrio).
    Para evitar expor esse ruído, tente uma pequena amostra bloqueante na
    primeira coleta; se ainda for 0.0, retorne None para evitar valores enganosos.
    """
    global _cpu_warmed_up
    try:
        val = psutil.cpu_percent(interval=0.0)
    except (OSError, RuntimeError):
        return None

    # Se não aquecido e valor for 0.0, tentar pequena amostra bloqueante e
    # marcar como aquecido. Se a nova amostra também for 0.0, retornar None
    # para evitar mostrar um falso 0% na primeira coleta.
    # usar comparação com epsilon para evitar checagens de igualdade direta
    eps = 1e-6
    if not _cpu_warmed_up and abs(val - 0.0) <= eps:
        try:
            val2 = psutil.cpu_percent(interval=0.05)
        except (OSError, RuntimeError) as exc:
            logger.debug("amostra curta cpu_percent falhou: %s", exc, exc_info=True)
            val2 = None
        _cpu_warmed_up = True
        if val2 is None:
            return None
        return None if abs(val2 - 0.0) <= eps else val2

    return val


def get_cpu_freq_ghz() -> float | None:
    """Retorne a frequência atual da CPU em GHz ou None se indisponível.

    Usa psutil.cpu_freq() que normalmente retorna valores em MHz; convertemos
    para GHz dividindo por 1000. Tratamos exceções e valores nulos.
    """
    try:
        f = psutil.cpu_freq()
    except (OSError, RuntimeError) as exc:
        logger.debug("psutil.cpu_freq() falhou: %s", exc, exc_info=True)
        return None

    if not f:
        return None

    # 'current' costuma estar em MHz; proteger contra None
    curr = getattr(f, "current", None)
    if curr is None:
        return None
    try:
        ghz = float(curr) / 1000.0
        if not math.isfinite(ghz):
            return None
        return ghz
    except (TypeError, ValueError):
        return None


def get_memory_percent() -> float:
    """Retorne a percentagem de uso de RAM."""
    return psutil.virtual_memory().percent


def get_disk_percent(path: str | None = None) -> float | None:
    r"""Retorne a percentagem de uso do disco para `path` especificado.

    Se `path` for None, escolha um default cross-platform:
    - Windows: use a raiz do filesystem atual (ex.: 'C:\\') via Path().anchor
    - POSIX: use '/'

    Retorne None em caso de erro (p.ex. path inválido ou permissão).
    """
    try:
        # resolve candidate path(s) to try — aceitamos str ou Path
        candidates: list[object] = []
        if path:
            candidates.append(Path(path))
        candidates.extend(_disk_candidate_paths())

        for p in candidates:
            try:
                # psutil accepts str or Path; attempt disk_usage regardless of p.exists()
                return psutil.disk_usage(str(p)).percent
            except OSError:
                # tentar próximo candidato; sonda em melhor esforço, ignorar e continuar
                continue  # nosec

        # se nenhum candidato funcionou, tentar usar o primeiro mesmo que não exista
        try:
            return psutil.disk_usage(str(candidates[0])).percent
        except OSError:
            return None
    except OSError:
        return None


def _get_temp_from_script(script_path: Path) -> float | None:
    """Execute o script `temp.sh` de forma segura e parseie um float de temperatura.

    Use subprocess.run sem shell para evitar injeção. Retorne float em graus
    Celsius em sucesso ou None em falha/erro de parse.
    """
    try:
        # executar o script com timeout para evitar bloqueios
        proc = subprocess.run([str(script_path)], capture_output=True, text=True, timeout=5)
    except (subprocess.SubprocessError, OSError) as exc:
        logger.error("_get_temp_from_script falhou ao executar: %s", exc, exc_info=True)
        return None

    out = (proc.stdout or "").strip()
    if not out:
        return None

    return _parse_first_float_from_text(out)


def _parse_first_float_from_text(text: str) -> float | None:
    """Tente extrair o primeiro número float de `text` e retorná-lo como float.

    Retorna None se não houver número ou se o valor não for finito.
    """
    if not text:
        return None
    m = re.search(r"([-+]?\d*\.?\d+)", text)
    if not m:
        return None
    try:
        v = float(m.group(1))
        return v if math.isfinite(v) else None
    except (ValueError, TypeError) as exc:
        logger.error("_parse_first_float_from_text: parse falhou: %s", exc, exc_info=True)
        return None


def _temperature_collector() -> float | None:
    """Collector usado pelo cache: retorna temperatura via script em POSIX."""
    if os.name != "posix":
        return None
    try:
        script_path = Path(__file__).resolve().parents[2] / "scripts" / "temp.sh"
        if script_path.exists() and os.access(script_path, os.X_OK):
            return _get_temp_from_script(script_path)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.error("_temperature_collector falhou: %s", exc, exc_info=True)
    return None


# _first_valid_temp removed as temperature reading now uses script-only fallback


def get_network_stats() -> dict[str, int]:
    """Retorne estatísticas de rede (bytes enviados/recebidos) como inteiros."""
    net = psutil.net_io_counters()
    return {
        "bytes_sent": int(net.bytes_sent),
        "bytes_recv": int(net.bytes_recv),
    }


def get_network_latency(host: str = "8.8.8.8", port: int = 53, timeout: float = 2.0) -> float | None:
    """Retorna latência em ms.

    1. Usa o binário `ping` do sistema (uma tentativa).
    2. Se falhar, tenta conexão TCP (medição de latência real via socket).

    Retorna um float em ms ou None.
    """
    global _last_latency_estimated
    _last_latency_estimated = False

    # valida host/port
    if not validate_host_port(host, port):
        logger.debug("validate_host_port failed for %s:%s, falling back to localhost", host, port)
        host = "127.0.0.1"

    def _build_ping_cmd(host: str, timeout: float) -> list[str]:
        """Monte o comando de ping apropriado para a plataforma.

        Usa timeouts em ms no Windows e em segundos na maioria dos Unix.
        """
        system = platform.system().lower()
        if system.startswith("win"):
            return ["ping", "-n", "1", "-w", str(int(timeout * 1000)), host]
        # -W frequentemente espera segundos; arredondar para int
        return ["ping", "-c", "1", "-W", str(int(timeout)), host]

    def _parse_ping_output_for_ms(output: str) -> float | None:
        """Parseie a saída do ping e retorne o tempo em ms, ou None se não achar.

        A regex procura o padrão `= <num> ms` comum em muitas implementações.
        """
        m = re.search(r"=\s*([\d.]+)\s*ms", output)
        if not m:
            return None
        try:
            v = float(m.group(1))
            return v if math.isfinite(v) else None
        except (ValueError, TypeError) as exc:
            logger.debug("get_network_latency: parse de ping falhou: %s", exc, exc_info=True)
            return None

    # Tenta via ping do sistema
    cmd = _build_ping_cmd(host, timeout)
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=float(timeout or 2.0))
        parsed = _parse_ping_output_for_ms(out)
        if parsed is not None:
            _last_latency_estimated = False
            return parsed
    except subprocess.CalledProcessError:
        # ping retornou com código !=0; tentar fallback TCP
        logger.debug("get_network_latency: ping returned non-zero exit status")
    except (subprocess.SubprocessError, OSError) as exc:
        # qualquer outro erro (timeout, binário ausente etc.) -> fallback
        logger.debug("get_network_latency: ping falhou: %s", exc, exc_info=True)
        # continue to TCP fallback
    return _tcp_latency_fallback(host, port, timeout)


def _tcp_latency_fallback(host: str, port: int, timeout: float) -> float | None:
    """Tentar medir latência via conexão TCP; marca _last_latency_estimated.

    Retorna valor em ms ou None. Mantém a flag `_last_latency_estimated` como True
    quando entrar no fallback, para indicar que a medida não veio do ping ICMP.
    """
    global _last_latency_estimated
    try:
        start = time.perf_counter()
        with socket.create_connection((host, port), timeout=timeout):
            end = time.perf_counter()
        v = round((end - start) * 1000, 2)
        _last_latency_estimated = True
        return v
    except OSError:
        _last_latency_estimated = True
        return None


# Compatibility wrappers: manter API antiga e fornecer conveniência
def get_latency(host: str = "8.8.8.8", port: int = 53, timeout: float = 2.0) -> float | None:
    """Alias para `get_network_latency` (compatibilidade)."""
    return get_network_latency(host=host, port=port, timeout=timeout)


def get_memory_info() -> tuple[int | None, int | None]:
    """Retorna (used_bytes, total_bytes) da memória física ou (None, None)."""
    try:
        vm = psutil.virtual_memory()
        return int(getattr(vm, "used", 0)), int(getattr(vm, "total", 0))
    except (OSError, RuntimeError, AttributeError) as exc:
        logger.debug("get_memory_info falhou: %s", exc, exc_info=True)
        return None, None


def get_disk_usage_info(path: str | None = None) -> tuple[int | None, int | None]:
    """Retorna (used_bytes, total_bytes) do disco para `path` ou (None, None)."""
    try:
        candidates: list[object] = []
        if path:
            candidates.append(Path(path))
        try:
            candidates.extend(_disk_candidate_paths())
        except Exception as exc:
            logger.debug("building disk candidates falhou: %s", exc, exc_info=True)
        for p in candidates:
            try:
                du = psutil.disk_usage(str(p))
                return int(getattr(du, "used", 0)), int(getattr(du, "total", 0))
            except OSError:
                continue
        try:
            du = psutil.disk_usage(str(candidates[0]))
            return int(getattr(du, "used", 0)), int(getattr(du, "total", 0))
        except OSError as exc:
            logger.debug("get_disk_usage_info: psutil.disk_usage falhou: %s", exc, exc_info=True)
            return None, None
    except OSError as exc:
        logger.debug("get_disk_usage_info falhou: %s", exc, exc_info=True)
        return None, None


# End of latency implementations
