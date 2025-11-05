import logging
import importlib

import pytest


settings_mod = importlib.import_module("src.config.settings")


def test_coerce_threshold_invalid_types():
    """Teste para tipos inválidos em _coerce_threshold."""
    with pytest.raises(ValueError):
        settings_mod._coerce_threshold("cpu_percent", "not-a-dict")

    with pytest.raises(ValueError):
        settings_mod._coerce_threshold("cpu_percent", {"warning": "a", "critical": "b"})


def test_coerce_threshold_order_and_range():
    """Teste para ordem e faixa de thresholds em _coerce_threshold."""
    # warning >= critical
    with pytest.raises(ValueError):
        settings_mod._coerce_threshold("cpu_percent", {"warning": 90, "critical": 80})

    # out of 0-100 range for percent
    with pytest.raises(ValueError):
        settings_mod._coerce_threshold("cpu_percent", {"warning": -1, "critical": 200})


def test_validate_settings_defaults_and_missing_keys():
    """Teste para validação de defaults e chaves ausentes em settings."""
    s = {"thresholds": {}}
    res = settings_mod.validate_settings(s)
    assert "thresholds" in res
    # metric from METRIC_NAMES should exist
    assert "cpu_percent" in res["thresholds"]


def test_get_valid_thresholds_fallback_on_error(monkeypatch, caplog):
    """Teste para fallback em erro ao obter thresholds válidos."""
    caplog.set_level(logging.WARNING)

    # make validate_settings raise
    monkeypatch.setattr(settings_mod, "validate_settings", lambda s: (_ for _ in ()).throw(ValueError("bad")))

    out = settings_mod.get_valid_thresholds({"thresholds": {}})
    assert isinstance(out, dict)
    assert "cpu_percent" in out
    assert any("Falha ao validar settings" in r.message for r in caplog.records)


def test_load_settings_env_override(monkeypatch, tmp_path):
    """Teste para override de settings via variável de ambiente."""
    # create a fake .env file
    env_file = tmp_path / ".env"
    env_file.write_text("MONITORING_THRESHOLD_CPU_PERCENT_WARNING=20")

    monkeypatch.setenv("MONITORING_ENV_FILE", str(env_file))
    # ensure no other env var interferes
    monkeypatch.setenv("MONITORING_LOG_LEVEL", "DEBUG")

    cfg = settings_mod.load_settings()
    assert cfg["log_level"] == "DEBUG"
    # threshold override should apply
    assert float(cfg["thresholds"]["cpu_percent"]["warning"]) == 20.0
