"""Configurações do projeto de monitorização.

Carrega limites (thresholds), nível de logs e políticas de tratamento a partir do
ambiente e de um ficheiro .env no raiz do projeto.
"""

import os
from pathlib import Path

# ========================
# 0. Constantes e padrões globais
# ========================

# --- Module purpose
# Este módulo: carrega e normaliza configurações do projeto (limites, nível de logs, políticas de tratamento).

STATE_STABLE = "STABLE"
STATE_WARNING = "WARNING"
STATE_CRITIC = "CRITIC"

METRIC_NAMES = [
    "cpu_percent",
    "memory_percent",
    "disk_percent",
    "network_loss_percent",
    "network_latency_ms",
    "ping_ms",
    "temperature_celsius",
]

DEFAULT_THRESHOLDS = {
    "cpu_percent": {"warning": 75.0, "critic": 90.0},
    "memory_percent": {"warning": 75.0, "critic": 90.0},
    "disk_percent": {"warning": 80.0, "critic": 95.0},
    "network_loss_percent": {"warning": 2.0, "critic": 5.0},
    "network_latency_ms": {"warning": 100.0, "critic": 250.0},
    "ping_ms": {"warning": 100.0, "critic": 500.0},
    "temperature_celsius": {"warning": 70.0, "critic": 85.0},
}

DEFAULT_TREATMENT_POLICIES = {
    "sustained_crit_seconds": 5 * 60,
    "min_critical_alerts": 1,
    "treatment_cooldowns": {
        "cleanup_temp_files": 3 * 24 * 3600,
        "check_disk_usage": 24 * 3600,
        "trim_process_working_set_windows": 60 * 60,
        "reap_zombie_processes": 60 * 60,
        "reapply_network_config": 30 * 60,
    },
    "cleanup_temp_age_days": 7,
}


# ========================
# 1. Carregamento das configurações
# ========================


# Função principal do módulo; carrega todas as configurações do ambiente
def load_settings() -> dict:
    """Carrega configurações do ambiente e do arquivo .env.

    Retorna dicionário com thresholds, log_level e políticas de tratamento.
    """
    import logging

    logger = logging.getLogger(__name__)

    thresholds = {k: v.copy() for k, v in DEFAULT_THRESHOLDS.items()}

    project_root = Path(__file__).resolve().parents[2]
    env_path = Path(os.getenv("MONITORING_ENV_FILE", project_root / ".env"))

    env_items = _merge_env_items(env_path, logger)
    _apply_threshold_overrides(env_items, thresholds, logger)

    treatment_policies = DEFAULT_TREATMENT_POLICIES.copy()
    _apply_treatment_policies(env_items, treatment_policies, logger)

    return {
        "thresholds": thresholds,
        "log_level": (env_items.get("MONITORING_LOG_LEVEL") or os.getenv("MONITORING_LOG_LEVEL", "INFO")),
        "treatment_policies": treatment_policies,
    }


# ========================
# 2. Funções auxiliares para ambiente e overrides
# ========================


# Auxilia load_settings; criado para centralizar leitura do .env
def _read_env_file(path: Path | str) -> dict:
    """Lê variáveis do arquivo .env e retorna pares chave-valor.

    Ignora linhas inválidas e registra falhas de leitura para depuração.
    """
    import logging

    logger = logging.getLogger(__name__)
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
    except OSError as exc:
        logger.debug("falha a ler .env em %s: %s", p, exc)
        return {}
    return result


# Auxilia load_settings; criado para unir variáveis do ambiente e .env
def _merge_env_items(env_path: Path, logger) -> dict:
    """Combina variáveis do .env com as do processo.

    Prioriza valores do arquivo .env e complementa com os do ambiente.
    """
    env_items = _read_env_file(env_path)
    if env_items == {} and env_path.exists():
        logger.warning("Erro ou ficheiro .env vazio em %s", env_path)
    for k, v in os.environ.items():
        env_items.setdefault(k, v)
    return env_items


# Auxilia load_settings; criado para aplicar overrides de thresholds
def _apply_threshold_overrides(env_items: dict, thresholds: dict, logger) -> None:
    """Atualiza thresholds conforme variáveis de ambiente.

    Ignora valores inválidos e registra avisos sem interromper inicialização.
    """
    for key, raw_val in env_items.items():
        if not key.startswith("MONITORING_THRESHOLD_"):
            continue
        rest = key[len("MONITORING_THRESHOLD_") :]
        metric, sep, kind = rest.rpartition("_")
        if not sep:
            logger.debug("Ignorando chave de limite (threshold) malformada: %s", key)
            continue
        metric = metric.lower()
        kind = kind.lower()
        if metric not in thresholds:
            logger.debug("Métrica desconhecida em limites (thresholds): %s", metric)
            continue
        if kind not in ("warning", "critic"):
            logger.debug("Tipo de limite (threshold) desconhecido para %s: %s", metric, kind)
            continue
        try:
            thresholds[metric][kind] = float(raw_val)
        except (TypeError, ValueError):
            logger.warning("Valor inválido para %s: %s", key, raw_val)


# Auxilia load_settings; criado para aplicar overrides nas políticas de tratamento
def _apply_treatment_policies(env_items: dict, treatment_policies: dict, logger) -> None:
    """Atualiza políticas de tratamento conforme variáveis de ambiente.

    Ignora valores inválidos e registra avisos sem interromper inicialização.
    """
    if "MONITORING_SUSTAINED_CRIT_SECONDS" in env_items:
        try:
            treatment_policies["sustained_crit_seconds"] = int(env_items["MONITORING_SUSTAINED_CRIT_SECONDS"])
        except (TypeError, ValueError):
            logger.warning(
                "MONITORING_SUSTAINED_CRIT_SECONDS inválido: %s",
                env_items.get("MONITORING_SUSTAINED_CRIT_SECONDS"),
            )
    if "MONITORING_MIN_CRITICAL_ALERTS" in env_items:
        try:
            treatment_policies["min_critical_alerts"] = int(env_items["MONITORING_MIN_CRITICAL_ALERTS"])
        except (TypeError, ValueError):
            logger.warning(
                "MONITORING_MIN_CRITICAL_ALERTS inválido: %s",
                env_items.get("MONITORING_MIN_CRITICAL_ALERTS"),
            )
    if "MONITORING_CLEANUP_TEMP_AGE_DAYS" in env_items:
        try:
            treatment_policies["cleanup_temp_age_days"] = int(env_items["MONITORING_CLEANUP_TEMP_AGE_DAYS"])
        except (TypeError, ValueError):
            logger.warning(
                "MONITORING_CLEANUP_TEMP_AGE_DAYS inválido: %s",
                env_items.get("MONITORING_CLEANUP_TEMP_AGE_DAYS"),
            )
    for k, v in env_items.items():
        if not k.startswith("MONITORING_TREATMENT_COOLDOWN_"):
            continue
        name = k[len("MONITORING_TREATMENT_COOLDOWN_") :].lower()
        try:
            sec = int(v)
            treatment_policies.setdefault("treatment_cooldowns", {}).update({name: sec})
        except (TypeError, ValueError):
            logger.warning("MONITORING_TREATMENT_COOLDOWN_%s inválido: %s", name, v)


# ========================
# 3. Validação e normalização dos thresholds
# ========================


# Auxilia validate_settings; criado para garantir tipos e limites corretos
def _coerce_threshold(metric_name: str, raw_value: dict) -> dict:
    """Valida e converte thresholds para tipos corretos.

    Garante que warning < critic e valores estejam dentro dos limites esperados.
    """
    if not isinstance(raw_value, dict):
        raise ValueError(f"threshold para {metric_name} deve ser um dict com chaves 'warning' e 'critic'")
    if "warning" not in raw_value or "critic" not in raw_value:
        raise ValueError(f"threshold para {metric_name} deve conter chaves 'warning' e 'critic': {raw_value!r}")
    try:
        warning_v = float(raw_value["warning"])
        critic_v = float(raw_value["critic"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"valores de threshold para {metric_name} devem ser numéricos: {raw_value!r}") from exc

    if warning_v >= critic_v:
        raise ValueError(f"threshold 'warning' deve ser < 'critic' para {metric_name}: {warning_v} >= {critic_v}")

    if (
        metric_name.endswith("_percent")
        or metric_name
        in (
            "cpu_percent",
            "memory_percent",
            "disk_percent",
            "network_loss_percent",
        )
    ) and not (0.0 <= warning_v <= 100.0 and 0.0 <= critic_v <= 100.0):
        raise ValueError(f"thresholds para {metric_name} devem ficar entre 0 e 100")

    return {"warning": warning_v, "critic": critic_v}


# Função principal de validação; normaliza e valida configurações
def validate_settings(settings: dict) -> dict:
    """Normaliza e valida o dicionário de configurações.

    Garante que todos os thresholds estejam presentes e corretos.
    """
    import logging

    logger = logging.getLogger(__name__)
    if not isinstance(settings, dict):
        raise TypeError("settings deve ser um dict")

    raw_thresholds = settings.get("thresholds")
    if not isinstance(raw_thresholds, dict):
        raw_thresholds = {}

    normalized: dict = {}
    for metric in METRIC_NAMES:
        raw = raw_thresholds.get(metric)
        if raw is None:
            normalized[metric] = DEFAULT_THRESHOLDS.get(metric, {"warning": 0.0, "critic": 100.0}).copy()
            continue
        normalized[metric] = _coerce_threshold(metric, raw)

    settings["thresholds"] = normalized
    settings.setdefault("log_level", "INFO")
    logger.debug("settings validados e normalizados")
    return settings


# Auxilia outros módulos; retorna thresholds validados ou padrão em caso de erro
def get_valid_thresholds(settings: dict | None = None) -> dict:
    """Retorna thresholds validados a partir das configurações.

    Em caso de erro, retorna os thresholds padrão e registra aviso.
    """
    import logging

    logger = logging.getLogger(__name__)
    try:
        if settings is None:
            settings = load_settings()
        validated = validate_settings(settings)
        return validated.get("thresholds", {k: v.copy() for k, v in DEFAULT_THRESHOLDS.items()})
    except (TypeError, ValueError, OSError) as exc:
        logger.warning("Falha ao validar settings; usando limites padrão (DEFAULT_THRESHOLDS): %s", exc)
        return {k: v.copy() for k, v in DEFAULT_THRESHOLDS.items()}
