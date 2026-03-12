import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests


def _get_free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.skipif(os.getenv("RUN_E2E") != "1", reason="E2E opt-in: set RUN_E2E=1")
def test_http_health_and_metrics_smoke(tmp_path: Path):
    """Smoke-test HTTP `/health` and `/metrics` when E2E is enabled."""
    port = _get_free_local_port()

    env = dict(os.environ)
    env.pop("MONITORING_ENV_FILE", None)

    env.update(
        {
            "MONITORING_HTTP_ENABLE": "1",
            "MONITORING_HTTP_ADDR": "127.0.0.1",
            "MONITORING_HTTP_PORT": str(port),
            "MONITORING_EXPORTER_ENABLE": "1",
            "MONITORING_PROMTAIL_ENABLE": "0",
            "MONITORING_LOG_LEVEL": "ERROR",
            "MONITORING_LOG_ROOT": str(tmp_path / "logs"),
            "PYTHONUNBUFFERED": "1",
        }
    )

    project_root = Path(__file__).resolve().parents[2]

    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "src.main", "-i", "1", "-c", "0"],
        cwd=str(project_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 8.0
    last_err: Exception | None = None
    try:
        while time.monotonic() < deadline:
            try:
                r = requests.get(f"{base}/health", timeout=0.5)
                if r.status_code == 200:
                    break
            except Exception as exc:  # pragma: no cover
                last_err = exc
            time.sleep(0.1)
        else:
            out = ""
            if proc.stdout is not None:
                try:
                    out = proc.stdout.read()[-4000:]
                except Exception:
                    out = ""
            raise AssertionError(
                f"/health did not become ready (last_err={last_err}); tail=\n{out}"
            )

        health = requests.get(f"{base}/health", timeout=1.0)
        assert health.status_code == 200

        metrics = requests.get(f"{base}/metrics", timeout=1.0)
        assert metrics.status_code == 200
        assert metrics.text.strip()
        assert "# HELP" in metrics.text
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:  # pragma: no cover
            proc.kill()
            proc.wait(timeout=3)
