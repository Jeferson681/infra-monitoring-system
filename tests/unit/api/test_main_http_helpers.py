import json
import types
from types import SimpleNamespace
import os
import time

import pytest

from infra_monitoring.api.exporter import main_http


def make_handler():
    # create an uninitialized instance of HealthHandler
    h = main_http.HealthHandler.__new__(main_http.HealthHandler)
    return h


def test_value_to_prometheus():
    h = make_handler()
    assert h._value_to_prometheus(True) == "1"
    assert h._value_to_prometheus(False) == "0"
    assert h._value_to_prometheus(3) == "3"
    assert h._value_to_prometheus(3.14) == "3.14"
    assert h._value_to_prometheus(" 2.5 ") == "2.5"
    assert h._value_to_prometheus("true") == "1"
    assert h._value_to_prometheus("false") == "0"
    assert h._value_to_prometheus("not-a-number") is None


def test_get_process_metrics_prometheus_and_names(monkeypatch):
    # Mock psutil.Process to return deterministic values
    class DummyProc:
        def cpu_percent(self, interval=0.0):
            return 1.1

        def memory_percent(self):
            return 2.2

        def memory_info(self):
            return SimpleNamespace(rss=1234)

        def create_time(self):
            return time.time() - 5

        def num_threads(self):
            return 3

        def num_fds(self):
            return 7

    monkeypatch.setattr(main_http.psutil, "Process", lambda: DummyProc())
    h = make_handler()
    metrics = h._get_process_metrics(prefix="process_", prometheus=False)
    assert "process_cpu_percent" in metrics
    assert metrics["process_cpu_percent"] == 1.1

    pm = h._get_process_metrics(prefix="process_", prometheus=True)
    # prometheus mode should not contain duplicate prefix
    assert all(not k.startswith("process_process_") for k in pm.keys())


def test_format_prometheus_metrics_and_helpers(monkeypatch, tmp_path):
    h = make_handler()
    # system metrics as flat dict
    system_metrics = {"metric_a": 1, "metric_b": "true"}
    process_metrics = {"process_x": 2}
    out = h._format_prometheus_metrics(system_metrics, process_metrics)
    text = out.decode("utf-8")
    assert "monitoring_metric_a 1" in text
    assert "monitoring_metric_b 1" in text
    assert "process_x 2" in text

    # exercise load averages branch: monkeypatch getloadavg (may not exist on Windows)
    monkeypatch.setattr(main_http.os, "getloadavg", lambda: (0.1, 0.2, 0.3), raising=False)
    out2 = h._format_prometheus_metrics(system_metrics, process_metrics)
    assert b"monitoring_load_1" in out2


def test_get_cpu_temp_c_fallback_and_psutil(monkeypatch):
    h = make_handler()
    # psutil sensors path
    monkeypatch.setattr(main_http.psutil, "sensors_temperatures", lambda: {"t": [SimpleNamespace(current=45.0)]}, raising=False)
    assert h._get_cpu_temp_c({}) == 45.0

    # fallback to provided system_metrics dict
    sm = {"metrics": {"temperature_celsius": 55}}
    # ensure psutil.sensors_temperatures returns empty so fallback is used
    monkeypatch.setattr(main_http.psutil, "sensors_temperatures", lambda: {}, raising=False)
    assert h._get_cpu_temp_c(sm) == 55.0


def test_get_last_system_metrics_reads_file(monkeypatch, tmp_path):
    # create JSONL file
    d = tmp_path / "logs" / "json"
    d.mkdir(parents=True)
    fname = d / "monitoring-test.jsonl"
    lines = [json.dumps({"a": 1}), json.dumps({"b": 2})]
    fname.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(main_http, "SYSTEM_METRICS_JSONL_PATH", str(d))
    h = make_handler()
    m = h._get_last_system_metrics()
    assert m == {"b": 2}


def test_get_network_rates(monkeypatch):
    h = make_handler()
    # reset class-level state
    h.__class__._last_net = None
    h.__class__._last_net_ts = None

    class Counters:
        bytes_sent = 1000
        bytes_recv = 2000

    monkeypatch.setattr(main_http.psutil, "net_io_counters", lambda: Counters)
    # first call initializes and returns (None, None)
    r1 = h._get_network_rates()
    assert r1 == (None, None)

    # advance time and change counters
    monkeypatch.setattr(main_http, "time", SimpleNamespace(time=lambda: 1000))
    class Counters2:
        bytes_sent = 3000
        bytes_recv = 5000

    monkeypatch.setattr(main_http.psutil, "net_io_counters", lambda: Counters2)
    # ensure last_ts is older
    h.__class__._last_net_ts = 900
    h.__class__._last_net = (2000, 1000)
    in_mbps, out_mbps = h._get_network_rates()
    assert isinstance(in_mbps, float) or in_mbps is None


def test_process_num_fds_exception(monkeypatch):
    # ensure exception path when num_fds raises
    class DummyProc:
        def cpu_percent(self, interval=0.0):
            return 0

        def memory_percent(self):
            return 0

        def memory_info(self):
            return SimpleNamespace(rss=0)

        def create_time(self):
            return time.time()

        def num_threads(self):
            return 1

        def num_fds(self):
            raise RuntimeError("nope")

    monkeypatch.setattr(main_http.psutil, "Process", lambda: DummyProc())
    h = make_handler()
    # should not raise
    metrics = h._get_process_metrics(prefix="p_")
    assert "p_num_threads" in metrics


def test_cpu_temp_psutil_raises_and_fallback(monkeypatch):
    h = make_handler()
    # sensors_temperatures raises
    monkeypatch.setattr(main_http.psutil, "sensors_temperatures", lambda: (_ for _ in ()).throw(RuntimeError("boom")), raising=False)
    # fallback if provided
    assert h._get_cpu_temp_c({"temperature": 12}) == 12.0
