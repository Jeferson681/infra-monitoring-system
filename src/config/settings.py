"""Configurações globais, variáveis de ambiente e thresholds.

Docstrings em português.
"""

import os
from pathlib import Path

# Estados de alerta usados pelo fluxo mínimo
STATE_STABLE = "ESTAVEL"
STATE_ALERT = "ALERTA"
STATE_CRITIC = "CRITIC"

# Lista dos nomes de métricas esperadas no stub de coleta
METRIC_NAMES = [
    "cpu_percent",
    "memory_percent",
    "disk_percent",
    "network_loss_percent",
    "network_latency_ms",
    "ping_ms",
    "temperature_celsius",
]

# Thresholds padrão (alert / critic) — valores de exemplo para o stub
DEFAULT_THRESHOLDS = {
    "cpu_percent": {"alert": 75.0, "critic": 90.0},
    "memory_percent": {"alert": 75.0, "critic": 90.0},
    "disk_percent": {"alert": 80.0, "critic": 95.0},
    # perda de pacotes em porcentagem
    "network_loss_percent": {"alert": 2.0, "critic": 5.0},
    # latência/tempo de ida em ms
    "network_latency_ms": {"alert": 100.0, "critic": 250.0},
    # ping (ms) — usado quando aplicável
    "ping_ms": {"alert": 100.0, "critic": 500.0},
    # temperatura em Celsius
    "temperature_celsius": {"alert": 70.0, "critic": 85.0},
}

# Diretório raiz de logs relativo à raiz do projection.
# Permite sobrescrever via variável de ambiente MONITORING_LOG_ROOT.
# Preferimos um diretório em lowercase ('logs') por padrão para evitar
# problemas de case-sensitive em alguns sistemas de ficheiros.
_raw_log_root = os.getenv("MONITORING_LOG_ROOT", "logs")
if isinstance(_raw_log_root, str):
    _raw_log_root = _raw_log_root.strip()
else:
    _raw_log_root = "logs"
if _raw_log_root == "Logs":
    LOG_ROOT = "logs"
else:
    LOG_ROOT = _raw_log_root or "logs"
# Nome do ficheiro de debug dentro de LOG_ROOT
DEBUG_LOG_FILENAME = "debug_log"


def _read_env_file(path) -> dict:
    """Lê um ficheiro .env simples e retorna um dict de chaves/valores.

    Comentários e linhas vazias são ignoradas. Não lança exceções para erro de
    I/O; retorna um dict vazio e deixa o logging para o chamador.
    """
    result: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return result
    try:
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                result[key] = val
    except Exception:
        # caller irá logar; aqui evitamos crash
        return {}
    return result


def load_settings() -> dict:
    """Carrega settings de `.env` e variáveis de ambiente, retornando um dict.

    Para sobrescrever thresholds, use chaves do tipo
    `MONITORING_THRESHOLD_<metric>_<ALERT|CRITIC>` no .env ou nas env vars do
    sistema.
    """
    import logging

    logger = logging.getLogger(__name__)

    # Começar com uma cópia dos defaults
    thresholds = {k: v.copy() for k, v in DEFAULT_THRESHOLDS.items()}

    project_root = Path(__file__).resolve().parents[2]
    env_path = Path(os.getenv("MONITORING_ENV_FILE", project_root / ".env"))

    env_items = _read_env_file(env_path)
    if env_items == {} and env_path.exists():
        logger.warning(
            "Erro ou ficheiro .env vazio em %s",
            env_path,
        )

    # adicionar variáveis de ambiente do processo caso não existam no ficheiro
    for k, v in os.environ.items():
        env_items.setdefault(k, v)

    # Aplicar overrides de thresholds
    for key, raw_val in env_items.items():
        if not key.startswith("MONITORING_THRESHOLD_"):
            continue
        rest = key[len("MONITORING_THRESHOLD_") :]  # correct slice (no E203)
        metric, sep, kind = rest.rpartition("_")
        if not sep:
            logger.debug(
                "Ignorando chave de threshold malformada: %s",
                key,
            )
            continue
        metric = metric.lower()
        kind = kind.lower()
        if metric not in thresholds:
            logger.debug(
                "Métrica desconhecida em thresholds: %s",
                metric,
            )
            continue
        if kind not in ("alert", "critic"):
            logger.debug(
                "Tipo de threshold desconhecido para %s: %s",
                metric,
                kind,
            )
            continue
        try:
            thresholds[metric][kind] = float(raw_val)
        except Exception:
            logger.warning(
                "Valor inválido para %s: %s",
                key,
                raw_val,
            )

    return {
        "thresholds": thresholds,
        "log_level": (env_items.get("MONITORING_LOG_LEVEL") or os.getenv("MONITORING_LOG_LEVEL", "INFO")),
    }


def _coerce_threshold(metric_name: str, raw_value: dict) -> dict:
    """Coerce um threshold bruto para a forma normalizada (nível de módulo).

    Lança ValueError para formatos inválidos.
    """
    if not isinstance(raw_value, dict):
        raise ValueError(f"threshold for {metric_name} must be a dict with 'alert' " f"and 'critic'")
    if "alert" not in raw_value or "critic" not in raw_value:
        raise ValueError(f"threshold for {metric_name} must contain 'alert' and 'critic' " f"keys: {raw_value!r}")
    try:
        alert_v = float(raw_value["alert"])
        critic_v = float(raw_value["critic"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"threshold values for {metric_name} must be numeric: {raw_value!r}") from exc

    if alert_v >= critic_v:
        raise ValueError(f"threshold alert must be < critic for {metric_name}: {alert_v} " f">= {critic_v}")

    if metric_name.endswith("_percent") or metric_name in (
        "cpu_percent",
        "memory_percent",
        "disk_percent",
        "network_loss_percent",
    ):
        if not (0.0 <= alert_v <= 100.0 and 0.0 <= critic_v <= 100.0):
            raise ValueError(f"thresholds for {metric_name} must be between 0 and 100")

    return {"alert": alert_v, "critic": critic_v}


# (validate_settings(settings: dict) abaixo implementa a validação real)


def get_thresholds() -> dict:
    """Return hard-coded thresholds for the minimal stub flow.

    Structure returned:
    {
        "metric_name": {"alert": float, "critic": float},
        ...
    }

    These values are placeholders for the stub and can be replaced by real
    configuration later.
    """
    # Para o stub, retornamos uma cópia da constante DEFAULT_THRESHOLDS.
    # Isso deixa o local centralizado para futuras configurações dinâmicas.
    return {k: v.copy() for k, v in DEFAULT_THRESHOLDS.items()}


def validate_settings(settings: dict) -> dict:
    """Valida e normaliza o dicionário de settings.

    - Garante que exista a key 'thresholds' como dict
    - Para cada métrica em METRIC_NAMES garante que exista {'alert', 'critic'}
      e que alert < critic. Coerção para float é realizada quando possível.
    - Preenche thresholds ausentes com DEFAULT_THRESHOLDS.

    Lança ValueError em caso de erro grave de formato ou de ranges inválidos.
    Retorna o dict de settings normalizado.
    """
    import logging

    logger = logging.getLogger(__name__)
    if not isinstance(settings, dict):
        raise TypeError("settings must be a dict")

    raw_thresholds = settings.get("thresholds")
    if not isinstance(raw_thresholds, dict):
        raw_thresholds = {}

    normalized: dict = {}
    for metric in METRIC_NAMES:
        raw = raw_thresholds.get(metric)
        if raw is None:
            normalized[metric] = DEFAULT_THRESHOLDS.get(metric, {"alert": 0.0, "critic": 100.0}).copy()
            continue
        normalized[metric] = _coerce_threshold(metric, raw)

    settings["thresholds"] = normalized
    settings.setdefault("log_level", "INFO")
    logger.debug("Settings validated and normalized")
    return settings


def get_valid_thresholds(settings: dict | None = None) -> dict:
    """Retorna thresholds validados prontos para consumo pelo SystemState.

    Se `settings` for None, carrega via `load_settings()`. Em caso de falha na
    validação, faz fallback para `DEFAULT_THRESHOLDS` e regista um warning.
    """
    import logging

    logger = logging.getLogger(__name__)
    try:
        if settings is None:
            settings = load_settings()
        validated = validate_settings(settings)
        return validated.get("thresholds", {k: v.copy() for k, v in DEFAULT_THRESHOLDS.items()})
    except Exception as exc:
        logger.warning(
            "Falha ao validar settings; usando DEFAULT_THRESHOLDS: %s",
            exc,
        )
        return {k: v.copy() for k, v in DEFAULT_THRESHOLDS.items()}
