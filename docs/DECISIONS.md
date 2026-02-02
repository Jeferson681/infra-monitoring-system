# Technical Decisions

This document consolidates the project’s main technical and architectural decisions (dependencies, data formats, and integration choices).
Previously, these decisions were spread across multiple files (`docs/DOCS.md`, `README.md`, `infra/terraform/README_TERRAFORM.md`) and were centralized here to make review, maintenance, and technical discussion easier.

---

## Architecture decisions

- **Host-aware collection with psutil**
	The project uses `psutil` to collect host metrics (CPU, memory, disk, and interfaces).
	**Rationale:** direct local collection, low dependency on external agents, and cross-platform compatibility.

- **JSONL format for export and archiving**
	The exporter writes and reads JSONL files for persistence and replay of metrics/logs.
	**Rationale:** incremental streaming-friendly format, easy pipeline ingestion, and good fit for integration tests.

- **Exporter activation via environment variable**
	Metrics exposure is controlled by `MONITORING_EXPORTER_ENABLE=1`.
	**Rationale:** explicit enablement by environment (local, CI), avoiding accidental exposure.

- **Persistence and replay**
	Persisted data lives under `logs/json/` (e.g., `logs/json/monitoring-YYYY-MM-DD.jsonl`) and can be reused by the exporter when exposing metrics.
	**Rationale:** deterministic replay and easier validation in tests and pipelines.

---

## Integration decisions

- **Observability-first architecture**
	Planned integration flow: exporter → Prometheus → Grafana, with Loki for logs.
	**Rationale:** enables local experimentation via Docker Compose and integration with real observability stacks.

- **Terraform as an IaC demonstration**
	The `infra/terraform` folder contains educational infra examples.
	**Rationale:** demonstrate IaC concepts without making Terraform part of the core runtime or the local metrics collection.

---

## Criteria for future changes

- Any relevant structural change (e.g., moving/renaming documentation files) should:
	1. Preserve a backup under `docs/originals/`
	2. Update impacted relative links
	3. Run a quick check (`pytest -q`) and verify exporter endpoints

---

## References

- `docs/DOCS.md`
- `README.md`
- `infra/terraform/README_TERRAFORM.md` (when applicable)
- `docs/diagrams/`
- `prints/`

Note: keep backups of original documents under `docs/originals/` before moving/renaming any documentation.
