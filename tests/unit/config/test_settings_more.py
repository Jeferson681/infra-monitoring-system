import importlib
import inspect
import logging

import pytest

settings_mod = importlib.import_module("infra_monitoring.infra.config.settings")


def test_coerce_threshold_invalid_types():
    """_coerce_threshold deve rejeitar tipos inválidos com mensagens claras."""
    with pytest.raises(ValueError) as excinfo:
        settings_mod._coerce_threshold("cpu_percent", "not-a-dict")
    assert "must be a dict" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo2:
        settings_mod._coerce_threshold("cpu_percent", {"warning": "a", "critical": "b"})
    assert "must be numeric" in str(excinfo2.value)


def test_coerce_threshold_order_and_range():
    """_coerce_threshold valida ordem e faixa (0-100 para percentuais)."""
    # warning >= critical
    with pytest.raises(ValueError) as excinfo:
        settings_mod._coerce_threshold("cpu_percent", {"warning": 90, "critical": 80})
    assert "must be < 'critical'" in str(excinfo.value)

    # out of 0-100 range for percent
    with pytest.raises(ValueError) as excinfo2:
        settings_mod._coerce_threshold("cpu_percent", {"warning": -1, "critical": 200})
    assert "devem ficar entre 0 e 100" in str(excinfo2.value)


def test_validate_settings_defaults_and_missing_keys():
    """validate_settings deve preencher defaults e normalizar tipos."""
    s = {"thresholds": {}}
    res = settings_mod.validate_settings(s)
    assert "thresholds" in res and isinstance(res["thresholds"], dict)
    # metric from METRIC_NAMES should exist and have warning/critical floats
    assert "cpu_percent" in res["thresholds"]
    cpu = res["thresholds"]["cpu_percent"]
    assert isinstance(cpu["warning"], float) and isinstance(cpu["critical"], float)
    # default should match DEFAULT_THRESHOLDS for a known metric
    assert cpu["warning"] == settings_mod.DEFAULT_THRESHOLDS["cpu_percent"]["warning"]


def test_public_api_signatures():
    # sanity-check signatures to prevent accidental API changes
    fn = getattr(settings_mod, "get_valid_thresholds", None)
    assert fn is not None and callable(fn)
    assert len(inspect.signature(fn).parameters) >= 1


def test_get_valid_thresholds_fallback_on_error(monkeypatch, caplog):
    """get_valid_thresholds deve retornar DEFAULT_THRESHOLDS em caso de erro."""
    caplog.set_level(logging.WARNING)

    # make validate_settings raise
    monkeypatch.setattr(
        settings_mod,
        "validate_settings",
        lambda s: (_ for _ in ()).throw(ValueError("bad")),
    )

    out = settings_mod.get_valid_thresholds({"thresholds": {}})
    assert isinstance(out, dict)
    assert "cpu_percent" in out
    assert any(
        "Failed to validate settings" in rec.getMessage() for rec in caplog.records
    )


def test_load_settings_env_override(monkeypatch, tmp_path):
    """load_settings deve aplicar override do arquivo .env e preservar tipos."""
    # create a fake .env file
    env_file = tmp_path / ".env"
    env_file.write_text("MONITORING_THRESHOLD_CPU_PERCENT_WARNING=20")

    monkeypatch.setenv("MONITORING_ENV_FILE", str(env_file))
    # ensure no other env var interferes
    monkeypatch.setenv("MONITORING_LOG_LEVEL", "DEBUG")

    cfg = settings_mod.load_settings()
    assert cfg["log_level"] == "DEBUG"
    # threshold override should apply and be numeric
    assert isinstance(cfg["thresholds"]["cpu_percent"]["warning"], float)
    assert cfg["thresholds"]["cpu_percent"]["warning"] == 20.0
    # other thresholds should remain present and be floats
    assert isinstance(cfg["thresholds"].get("memory_percent"), dict)
    assert isinstance(cfg["thresholds"]["memory_percent"]["warning"], float)
