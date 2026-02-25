# Terraform Examples — Educational / Demonstrative Use

This folder contains Terraform example files that demonstrate Infrastructure as Code (IaC) concepts in the context of this project.
These files can be used freely for study, local tests, or controlled provisioning of simple environments.

## Important notes

The examples are minimal and illustrative, focused on understanding blocks, variables, and provisioning flows.

Before applying to any real environment, review and adapt to your needs (networking, security, IAM policies, remote backend, etc.).

Remote state and concurrency locking are not configured by default.

## What this example mirrors in the repo

This Terraform is intentionally **conceptual** and is kept aligned with the current Docker structure:

- Docker build/compose lives under `docker/` (see `docker/Dockerfile` and `docker/docker-compose.yml`).
- The Compose file runs **one image** with two different containers/commands:
	- `infra-monitoring-system_app`: `python -m src.main` (main loop)
	- `infra-monitoring-main-http`: `python -u -m infra_monitoring.api.exporter.main_http` (HTTP exporter on port 8000)

Terraform mirrors the same idea via two small modules under `infra/terraform/modules/`.

Note: this example does **not** provision the full observability stack from Compose (Prometheus/Grafana/Loki/Promtail). It stays intentionally minimal and didactic.

### Local syntax validation

```sh
cd infra/terraform
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
```

### Safe execution in a test environment

```sh
terraform plan
terraform apply
```

Recommendation: use an isolated account or workspace to avoid unintended changes to critical environments.

## Notes about volumes and .env

The Compose setup mounts folders like `logs/`, `reports/` and `.cache/` and uses an `.env` file.
The Terraform example keeps `*_volume_mounts` empty by default so `terraform validate` stays cross-platform and CI-friendly.
If you ever apply it locally, pass volume mounts explicitly via variables.

---

For details on collection limits (`psutil`), persistence (JSONL), and exporter activation, see `docs/DECISIONS.md`. Run instructions and examples are in `docs/RUN.md`.

---
## Summary

Terraform usage in this project is fully optional.
It serves as a didactic base and can be adapted for real deployments, considering the differences between physical host metrics and metrics from the provisioned environment.
