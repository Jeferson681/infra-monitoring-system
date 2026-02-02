# Architecture

Vision: this project is an observability-first monitoring exporter — a lightweight collector that turns local signals into metrics and logs consumable by Prometheus/Grafana/Loki. The core runs as Python processes under `src/` and can run locally (venv) or via Docker Compose for end-to-end experimentation.

Scope/limits: the exporter collects host-aware metrics (via `psutil`) and writes/reads JSONL under `logs/json/` for persistence and replay. It is not intended to be a universal remote agent. More complex integrations (federation, long-term storage, remote collection) are out of scope and can be delegated to external infra (remote Prometheus, object storage, etc.).

Main components:

- Exporter (`src/`): collects metrics and exposes HTTP endpoints when enabled by environment.
- JSONL persistence: `logs/json/` acts as an ingest/test source and a handoff file format.
- Observability stack: Prometheus for scraping, Grafana for visualization, Loki for logs.
- Infra (optional): `infra/terraform` contains educational IaC examples.

Planned evolution: modular collectors (plugins), authentication/TLS, optional long-term retention backend, and more integration/load testing. If you move/rename visual artifacts, keep them under `prints/` and update relative links.

Diagram: see `prints/architecture.png` for a visual representation of limits and flows.
