import re

import infra_monitoring.services.monitoring.formatters as formatters


def test_normalize_for_display_basic():
    """normalize_for_display returns a dict with 'metrics_raw' and preserved keys."""
    metrics = {"cpu": 1.5, "mem": 2.0}
    out = formatters.normalize_for_display(metrics)
    assert isinstance(out, dict)
    assert "metrics_raw" in out and isinstance(out["metrics_raw"], dict)
    assert "cpu" in out["metrics_raw"] and "mem" in out["metrics_raw"]
    # returned summaries must be strings when present
    if out.get("summary_short") is not None:
        assert isinstance(out["summary_short"], str)


def test_format_duration():
    """format_duration must return a human readable duration string."""
    # Accept either compact '1m 5s' or HH:MM:SS formats; check for minutes and seconds
    result = formatters.format_duration(65)
    assert isinstance(result, str)
    # require that minutes and seconds appear in some form
    assert (re.search(r"1\s*m", result) and re.search(r"5\s*s", result)) or re.match(
        r"0:\d{2}:\d{2}", result
    )

    result = formatters.format_duration(3600)
    assert isinstance(result, str)
    assert re.search(r"1\s*h", result) or re.match(r"1:00:00", result)
