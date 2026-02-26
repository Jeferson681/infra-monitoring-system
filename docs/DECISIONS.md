# Technical Decisions

This document consolidates the project’s main technical and architectural decisions
(dependencies, data formats, integration choices and structural trade-offs).

The decisions in v1.x intentionally prioritize foundational engineering and
architectural clarity. Certain components were implemented directly rather
than delegated to external libraries in order to deepen understanding of
observability mechanics and maintain explicit system boundaries.

Future major versions may strategically replace specific internal
implementations with industry-standard tooling where interoperability,
maintainability and production alignment justify the transition.

Previously, these decisions were spread across multiple files
(`docs/DOCS.md`, `README.md`, `infra/terraform/README_TERRAFORM.md`)
and were centralized here to make review, maintenance, and technical
discussion easier.

---

## Architecture decisions

- **Host-aware collection with psutil**
	The project uses `psutil` to collect host metrics (CPU, memory, disk, and interfaces).
	**Rationale:** direct local collection, low dependency on external agents,
	cross-platform compatibility, and full control over metric shaping
	and aggregation logic.

- **JSONL format for export and archiving**
	The exporter writes and reads JSONL files for persistence and replay of metrics/logs.
	**Rationale:** incremental streaming-friendly format, deterministic replay capability,
	and clear separation between collection and exposition layers.

- **Exporter activation via environment variable**
	Metrics exposure is controlled by `MONITORING_EXPORTER_ENABLE=1`.
	**Rationale:** explicit enablement by environment (local, CI),
	avoiding accidental exposure and preserving runtime control boundaries.

- **Persistence and replay strategy**
	Persisted data lives under `logs/json/`
	(e.g., `logs/json/monitoring-YYYY-MM-DD.jsonl`)
	and can be reused by the exporter when exposing metrics.
	**Rationale:** deterministic replay, reproducibility in tests and pipelines,
	and separation between data generation and HTTP exposition.

---

## Integration decisions

- **Observability-first architecture**
	Planned integration flow: exporter → Prometheus → Grafana, with Loki for logs.
	**Rationale:** enables local experimentation via Docker Compose while maintaining
	compatibility with real observability stacks.

- **Controlled abstraction level (v1.x)**
	Core instrumentation logic is implemented within the project boundary
	instead of relying immediately on external observability SDKs.
	**Rationale:** establish architectural ownership, understand internal mechanics,
	and prepare the system for deliberate abstraction in future major versions.

- **Terraform as an IaC demonstration**
	The `infra/terraform` folder contains educational infrastructure examples.
	**Rationale:** demonstrate Infrastructure as Code concepts without making
	Terraform part of the core runtime or local metrics collection process.

---

## Criteria for future changes

Any relevant structural change (e.g., moving/renaming documentation files) should:

1. Preserve a backup under `docs/originals/`
2. Update impacted relative links
3. Run a quick validation (`pytest -q`) and verify exporter endpoints

Architectural evolution should preserve modular boundaries and avoid
disruptive rewrites. Refactoring must prioritize clarity, testability
and interoperability.

---

## References

- `docs/DOCS.md`
- `README.md`
- `infra/terraform/README_TERRAFORM.md` (when applicable)
- `docs/diagrams/`
- `prints/`

Note: keep backups of original documents under `docs/originals/`
before moving/renaming any documentation.
