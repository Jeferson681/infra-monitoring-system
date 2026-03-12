"""Runtime configuration and threshold definitions.

This module centralizes default thresholds, log level defaults and treatment
policy definitions. Values may be overridden via environment variables or a
project ``.env`` file. Public helpers load and validate settings used by the
monitoring loop and treatment subsystems.
"""

import os
from pathlib import Path

from infra_monitoring.infra.system.helpers import merge_env_items, read_env_file

# Global constants and defaults
STATE_STABLE = "STABLE"
STATE_WARNING = "WARNING"
STATE_CRITICAL = "CRITICAL"

METRIC_NAMES = [
    "cpu_percent",
    "memory_percent",
    "disk_percent",
    "network_loss_percent",
    "network_latency_ms",
    # aliases / nomes alternativos usados em outras partes do código
    "latency_ms",
    "temperature",
    # nomes de métricas em bytes usados por averages/state
    "memory_used_bytes",
    "memory_total_bytes",
    "disk_used_bytes",
    "disk_total_bytes",
    "bytes_sent",
    "bytes_recv",
    "ping_ms",
    "temperature_celsius",
]

DEFAULT_THRESHOLDS = {
    "cpu_percent": {"warning": 75.0, "critical": 90.0},
    "memory_percent": {"warning": 75.0, "critical": 90.0},
    "disk_percent": {"warning": 80.0, "critical": 95.0},
    "network_loss_percent": {"warning": 2.0, "critical": 5.0},
    "network_latency_ms": {"warning": 100.0, "critical": 250.0},
    "ping_ms": {"warning": 100.0, "critical": 500.0},
    "temperature_celsius": {"warning": 70.0, "critical": 85.0},
    # valores padrão para aliases e métricas em bytes. São amplos por padrão
    # para evitar falsos positivos; ajuste via .env ou variáveis de ambiente.
    "latency_ms": {"warning": 100.0, "critical": 250.0},
    "temperature": {"warning": 70.0, "critical": 85.0},
    "memory_used_bytes": {"warning": 0.0, "critical": 1e18},
    "memory_total_bytes": {"warning": 0.0, "critical": 1e18},
    "disk_used_bytes": {"warning": 0.0, "critical": 1e18},
    "disk_total_bytes": {"warning": 0.0, "critical": 1e18},
    "bytes_sent": {"warning": 0.0, "critical": 1e18},
    "bytes_recv": {"warning": 0.0, "critical": 1e18},
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
# Settings loading


def load_settings() -> dict:
    """Load configuration by merging DEFAULTS + .env + environment.

    Returns a dict with keys:

    - "thresholds": effective thresholds
    - "log_level": configured log level
    - "treatment_policies": treatment policies

    Environment variables override values from the `.env` file.
    """
    import logging

    logger = logging.getLogger(__name__)

    thresholds = {k: v.copy() for k, v in DEFAULT_THRESHOLDS.items()}

    project_root = Path(__file__).resolve().parents[2]
    env_path = Path(os.getenv("MONITORING_ENV_FILE", project_root / ".env"))

    # Merge .env with process environment variables
    # If MONITORING_ENV_FILE is explicitly set, prefer the file over process
    # environment variables (useful for tests that create a temporary .env).
    # Otherwise keep the default behavior: process environment variables
    # override the .env file.
    process_env = dict(os.environ)
    if os.getenv("MONITORING_ENV_FILE"):
        file_items = read_env_file(env_path)
        env_items = dict(process_env)
        env_items.update(file_items)
    else:
        env_items = merge_env_items(env_path, process_env)
    _apply_threshold_overrides(env_items, thresholds, logger)

    treatment_policies = DEFAULT_TREATMENT_POLICIES.copy()
    _apply_treatment_policies(env_items, treatment_policies, logger)

    return {
        "thresholds": thresholds,
        "log_level": (
            env_items.get("MONITORING_LOG_LEVEL")
            or os.getenv("MONITORING_LOG_LEVEL", "INFO")
        ),
        "treatment_policies": treatment_policies,
    }


# Helper functions to apply overrides from the environment
def _apply_threshold_overrides(env_items: dict, thresholds: dict, logger) -> None:
    """Apply threshold overrides from ``env_items``.

    Looks for keys with prefix ``MONITORING_THRESHOLD_<METRIC>_<TYPE>``.
    """
    for key, raw_val in env_items.items():
        if not key.startswith("MONITORING_THRESHOLD_"):
            continue
        rest = key[len("MONITORING_THRESHOLD_") :]
        metric, sep, kind = rest.rpartition("_")
        if not sep:
            logger.debug("Ignoring malformed threshold key: %s", key)
            continue
        metric = metric.lower()
        kind = kind.lower()
        if metric not in thresholds:
            logger.debug("Unknown metric in thresholds: %s", metric)
            continue
        # accept aliases like 'crit' / 'CRIT' and normalize to 'critical'
        if kind.startswith("crit"):
            kind = "critical"
        # aceitar apenas tipos válidos
        if kind not in ("warning", "critical"):
            logger.debug("Unknown threshold type for %s: %s", metric, kind)
            continue
        try:
            thresholds[metric][kind] = float(raw_val)
        except (TypeError, ValueError):
            logger.warning("Invalid value for %s: %s", key, raw_val)


# Assists load_settings; apply overrides to treatment policies
def _apply_treatment_policies(
    env_items: dict, treatment_policies: dict, logger
) -> None:
    """Apply treatment policy overrides from environment variables.

    E.g. ``MONITORING_SUSTAINED_CRIT_SECONDS``.
    """
    if "MONITORING_SUSTAINED_CRIT_SECONDS" in env_items:
        try:
            treatment_policies["sustained_crit_seconds"] = int(
                env_items["MONITORING_SUSTAINED_CRIT_SECONDS"]
            )
        except (TypeError, ValueError):
            logger.warning(
                "MONITORING_SUSTAINED_CRIT_SECONDS invalid: %s",
                env_items.get("MONITORING_SUSTAINED_CRIT_SECONDS"),
            )
    if "MONITORING_MIN_CRITICAL_ALERTS" in env_items:
        try:
            treatment_policies["min_critical_alerts"] = int(
                env_items["MONITORING_MIN_CRITICAL_ALERTS"]
            )
        except (TypeError, ValueError):
            logger.warning(
                "MONITORING_MIN_CRITICAL_ALERTS invalid: %s",
                env_items.get("MONITORING_MIN_CRITICAL_ALERTS"),
            )
    if "MONITORING_CLEANUP_TEMP_AGE_DAYS" in env_items:
        try:
            treatment_policies["cleanup_temp_age_days"] = int(
                env_items["MONITORING_CLEANUP_TEMP_AGE_DAYS"]
            )
        except (TypeError, ValueError):
            logger.warning(
                "MONITORING_CLEANUP_TEMP_AGE_DAYS invalid: %s",
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
            logger.warning("MONITORING_TREATMENT_COOLDOWN_%s invalid: %s", name, v)


# Validation and normalization of thresholds


def _coerce_threshold(metric_name: str, raw_value: dict) -> dict:
    """Validate and coerce thresholds to correct types.

    Ensure that `warning` < `critical` and that values are within expected bounds.
    """
    if not isinstance(raw_value, dict):
        raise ValueError(
            f"threshold for {metric_name} must be a dict with 'warning' and 'critical' keys"
        )
    if "warning" not in raw_value or ("critical" not in raw_value):
        raise ValueError(
            f"threshold for {metric_name} must contain 'warning' and 'critical' keys: {raw_value!r}"
        )
    try:
        warning_v = float(raw_value["warning"])
        # use only the canonical key 'critical'
        critical_raw = raw_value["critical"]
        if critical_raw is None:
            raise TypeError("missing critical threshold")
        critical_v = float(critical_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"threshold values for {metric_name} must be numeric: {raw_value!r}"
        ) from exc

    if warning_v >= critical_v:
        raise ValueError(
            f"threshold 'warning' must be < 'critical' for {metric_name}: {warning_v} >= {critical_v}"
        )

    if (
        metric_name.endswith("_percent")
        or metric_name
        in (
            "cpu_percent",
            "memory_percent",
            "disk_percent",
            "network_loss_percent",
        )
    ) and not (0.0 <= warning_v <= 100.0 and 0.0 <= critical_v <= 100.0):
        raise ValueError(f"thresholds para {metric_name} devem ficar entre 0 e 100")

    return {"warning": warning_v, "critical": critical_v}


def validate_settings(settings: dict) -> dict:
    """Normalize and validate the settings dictionary.

    Returns `settings` with the `thresholds` key populated with coherent
    values and correct types.
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
            # ensure defaults for the metric when missing
            default = DEFAULT_THRESHOLDS.get(
                metric, {"warning": 0.0, "critical": 100.0}
            ).copy()
            normalized[metric] = default
            continue
        coerced = _coerce_threshold(metric, raw)
        normalized[metric] = coerced

    settings["thresholds"] = normalized
    settings.setdefault("log_level", "INFO")
    logger.debug("Settings validated and normalized")
    return settings


# Assists other modules; return validated thresholds or defaults on error
def get_valid_thresholds(settings: dict | None = None) -> dict:
    """Return validated thresholds from the settings.

    On error, return the default thresholds and log a warning.
    """
    import logging

    logger = logging.getLogger(__name__)
    try:
        if settings is None:
            settings = load_settings()
        validated = validate_settings(settings)
        return validated.get(
            "thresholds", {k: v.copy() for k, v in DEFAULT_THRESHOLDS.items()}
        )
    except (TypeError, ValueError, OSError) as exc:
        logger.warning(
            "Failed to validate settings; DEFAULT_THRESHOLDS will be used: %s", exc
        )
        return {k: v.copy() for k, v in DEFAULT_THRESHOLDS.items()}
