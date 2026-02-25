# How to Run (quick guide)

Goal: concise instructions to run the project locally (venv) and with Docker, plus quick checks.

## Prerequisites

- Python 3.13+
- `docker` and Docker Compose (optional, for the container flow)
- `pre-commit` (recommended) — runs quality and security hooks
- `hadolint` (optional) — `hadolint` is executed in CI during image scans. To run it locally use the `hadolint/hadolint` Docker image or install `hadolint` natively.

## Run flows (what to run)

This repo has two main runtime modes (same image/code, different commands):

- **App loop (collector):** `python -m src.main`
	- Collects metrics/logs and persists JSONL.
	- Can optionally start a fallback HTTP server when `MONITORING_HTTP_ENABLE=1`.
- **HTTP exporter service:** `python -m infra_monitoring.api.exporter.main_http`
	- Exposes `/health` and `/metrics`.
	- Used by Docker Compose as a dedicated service (`main_http`) to keep responsibilities separate.

## Local run (venv)

1) Create and activate a virtualenv

```powershell
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

or (Unix)

```bash
python -m venv .venv
source .venv/bin/activate
```

Note (Unix): this repo uses a `src/` layout; ensure `src/` is on `PYTHONPATH` when running directly from the repo:

```bash
export PYTHONPATH=src
```

2) Install dependencies

```bash
python -m pip install -r requirements.txt
```

3) Choose one of the flows

Notes:

- The `./.env` file in the repository root contains defaults (e.g., `MONITORING_EXPORTER_ADDR=127.0.0.1`). The `src.main` entrypoint tries to read it automatically and only sets variables that are not already present in the process environment (local-dev convenience). If you prefer controlling the environment externally, load `.env` in your shell before running.

PowerShell — load `.env` and run (useful for local tests):

```powershell
$env:PYTHONPATH = "$PWD\\src"
Get-Content .env | ForEach-Object {
	if ($_ -and $_ -notmatch '^\s*#') {
		$p = $_ -split '=',2
		if ($p.Length -eq 2) { [Environment]::SetEnvironmentVariable($p[0].Trim(), $p[1].Trim(), 'Process') }
	}
}
& .\.venv\Scripts\python.exe -u -m src.main -c 0 -i 1 -vv
```

### Flow A — app loop only (no HTTP)

This matches the default behavior in Compose for the `infra-monitoring-system` service.

```powershell
$env:PYTHONPATH = "$PWD\\src"
& .\.venv\Scripts\python.exe -u -m src.main -c 0 -i 1 -vv
```

### Flow B — app loop + fallback HTTP server

Use this when you want a single process to both collect and expose `/metrics` locally.

```powershell
$env:PYTHONPATH = "$PWD\\src"
$env:MONITORING_EXPORTER_ENABLE = '1'
$env:MONITORING_HTTP_ENABLE = '1'
# MONITORING_HTTP_ADDR não definido -> default é 127.0.0.1
& .\.venv\Scripts\python.exe -u -m src.main -c 0 -i 1 -vv
```

### Flow C — dedicated exporter service (main_http)

Use this when you want a dedicated `/metrics` process (the same design as Compose).

```powershell
$env:PYTHONPATH = "$PWD\\src"
$env:MONITORING_HTTP_ADDR = '127.0.0.1'
$env:MONITORING_HTTP_PORT = '8000'
& .\.venv\Scripts\python.exe -u -m infra_monitoring.api.exporter.main_http
```

```powershell
$env:PYTHONPATH = "$PWD\\src"
$env:MONITORING_EXPORTER_ENABLE = '1'
$env:MONITORING_HTTP_ENABLE = '1'
# MONITORING_HTTP_ADDR não definido -> default é 127.0.0.1
& .\.venv\Scripts\python.exe -u -m src.main -c 0 -i 1 -vv
```

Bind to all host interfaces (careful — external exposure):

```powershell
$env:PYTHONPATH = "$PWD\\src"
$env:MONITORING_EXPORTER_ENABLE = '1'
$env:MONITORING_HTTP_ENABLE = '1'
$env:MONITORING_HTTP_ADDR = '0.0.0.0'  # Risk: allows external access if the port is published
& .\.venv\Scripts\python.exe -u -m src.main -c 0 -i 1 -vv
```

## Docker / Docker Compose

`docker/docker-compose.yml` already includes services for `prometheus`, `grafana`, `loki`, `promtail`, the app service, and a dedicated `main_http` metrics service. By default, the compose file:

- does NOT publish the metrics port (`8000`) to the host;
- runs the metrics endpoint inside the compose network (scraped by Prometheus).

### Full stack (Compose)

Start compose (from the project root):

```bash
docker compose -f docker/docker-compose.yml up --build -d
```

Common endpoints when ports are published:
- Prometheus → http://localhost:9090
- Grafana → http://localhost:3000
- Loki → http://localhost:3100
- Exporter → http://localhost:8000/metrics (only if `ports:` is configured)

Compose note: `docker/docker-compose.yml` includes a `main_http` service that runs `infra_monitoring.api.exporter.main_http`; that’s why `observability/prometheus.yml` is configured to scrape `main_http:8000`. The main app service (`infra-monitoring-system`) can also start a fallback HTTP metrics server when `MONITORING_HTTP_ENABLE=1`, but in the default compose the metrics server is served by `main_http` to separate responsibilities.

### App-only (Docker)

If you want to run only the app loop container (without the full observability stack), build and run it directly:

```bash
docker build -f docker/Dockerfile -t infra-monitoring-system:local .
docker run --rm -e MONITORING_HTTP_ENABLE=0 infra-monitoring-system:local python -m src.main
```

### Exporter-only (Docker)

```bash
docker build -f docker/Dockerfile -t infra-monitoring-system:local .
docker run --rm -p 8000:8000 -e MONITORING_HTTP_ADDR=0.0.0.0 -e MONITORING_HTTP_PORT=8000 infra-monitoring-system:local \
	python -u -m infra_monitoring.api.exporter.main_http
```

## Quick checks

- Check `/metrics`:

```bash
curl -s http://127.0.0.1:8000/metrics | head
```

- Check JSONL persistence files: `logs/json/` (e.g., `logs/json/monitoring-YYYY-MM-DD.jsonl`).
- Run tests:

```bash
python -m pytest -q
```

### Pre-commit

Run all local hooks:

```powershell
python -m pip install --upgrade pip
python -m pip install pre-commit
pre-commit run --all-files
```

Note: `hadolint` runs in CI during image scans. To run it locally without installing it, run:

```powershell
docker run --rm -v "${PWD}":/data -w /data hadolint/hadolint:latest hadolint docker/Dockerfile
```

Or install `hadolint` natively and run `hadolint docker/Dockerfile`.

## Environment variables (metrics exposure and runtime)

Main variables that affect exposure and execution:

- `MONITORING_EXPORTER_ENABLE` (0|1) — initializes/registers metrics (calls `start_exporter()`); does not automatically start an HTTP server by itself.
- `MONITORING_EXPORTER_ADDR`, `MONITORING_EXPORTER_PORT` — defaults and metadata (e.g., `.env` sets `127.0.0.1`/8000).
- `MONITORING_HTTP_ENABLE` (0|1) — starts the fallback HTTP server that exposes `/metrics` and `/health` (implemented in `infra_monitoring.api.exporter.main_http`).


	Note: the main entrypoint (`src/main.py`) checks `MONITORING_HTTP_ENABLE` at runtime and, when set to `1`, starts the fallback HTTP server by calling the handler in `infra_monitoring.api.exporter.main_http`.
- `MONITORING_HTTP_ADDR`, `MONITORING_HTTP_PORT` — bind for the fallback HTTP server. Local default: `127.0.0.1`. Orchestrators may use `0.0.0.0` inside containers to allow scraping by other services.
- `MONITORING_PROMTAIL_ENABLE` (0|1) — starts the internal worker that sends heartbeats directly to Loki (complements the `promtail` service in compose).
- `MONITORING_INTERVAL_SEC`, `MONITORING_CYCLES` — interval and runtime controls; can also be set via CLI (`-i`, `-c`) — CLI takes precedence over env.

Best practices and recommendations:

- Keep the app default as `127.0.0.1` for local runs.
- In Docker Compose, use `MONITORING_HTTP_ADDR=0.0.0.0` **without** publishing ports (`ports:`) to limit exposure to the compose network (other containers), not the host.
- Only publish ports in `docker/docker-compose.yml` if you need to access `/metrics` from the host; if you publish, protect it with firewall/proxy/TLS as needed.
- To reduce runtime differences across services, standardize the Python base image used in your compose services (e.g., `python:3.13-slim`).
- For CI: keep security checks (Trivy) and Dockerfile linting (hadolint) to catch regressions.
- For tests that require synchronous post-treatment, use `POST_TREATMENT_SYNC=1`.

## Troubleshooting

- If `/metrics` does not show up: check `MONITORING_EXPORTER_ENABLE` and `MONITORING_EXPORTER_PORT`.
- Network/port permissions may block binding; use `127.0.0.1` for local tests.
- In containers, `psutil` collects the container context — use `node_exporter` for host-level metrics.

## Notes

- Important paths: `logs/json/`, `docs/prints/` (visual artifacts).
- Windows vs Unix: environment variable commands differ (see examples above).
