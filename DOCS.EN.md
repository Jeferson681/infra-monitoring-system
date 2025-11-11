# Infra Monitoring System — Technical Documentation

## 1. Purpose & Context

This system was developed for educational purposes and to demonstrate best practices in monitoring, automation, and continuous integration.
Implements collection and exposition of enriched metrics and logs, integrating with leading observability tools: **Prometheus**, **Grafana**, and **Loki**.

The focus is to demonstrate the complete flow of **collection → persistence → export → analysis** in an automated, versioned, and secure environment.

---

## 2. General Architecture

The system operates in two main containers:

- **monitoring-app** — runs the monitoring core (`main.py`), responsible for collecting, processing, and writing metrics in JSONL format.
- **monitoring-metrics** — runs the HTTP exporter (`main_http.py`), which reads JSONL and exposes metrics and logs on endpoints compatible with Prometheus and Loki.

Both share the `/logs` volume, ensuring Promtail can access `.log` and `.json` files.
The file `infra/promtail/promtail-config.yml` defines the default collection behavior for Loki.

> **Technical note:** The `monitoring-metrics` container is for demonstration. In production, collection should be done locally or via a dedicated agent, not inside monitoring containers.

---

## 3. Metrics & Logs Flow

### 3.1 Collection & Persistence
The main module collects system data (CPU, memory, disk, network, latency) and writes to rotating JSONL.
Logs are structured in JSON and stored in the same shared volume.

### 3.2 Export
The exporter reads the last line of JSONL and updates Prometheus *Gauges*, exposing only the current snapshot.

**Available endpoints:**
- `/health`: JSON summary of metrics.
- `/metrics`: Prometheus exposition format (plain text).

### 3.3 Process Metrics
Python process metrics (CPU, memory, threads, uptime, descriptors) are collected in real time and not persisted.

> **Recommendation:** Align Prometheus `scrape_interval` with the monitoring collection interval.

---

## 4. Observability & Integration

Integration occurs via containers defined in `docker-compose.yml` and Terraform modules (`infra/terraform/main.tf`).
Environment variables and volumes should be reviewed according to the execution environment.

**Applied best practices:**
- Standardized, structured logs.
- Native Prometheus metrics.
- Isolated containers with controlled volumes.
- End-to-end integration (collection → export → visualization).

**Default access:**
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Loki: http://localhost:3100

---

## 5. Infrastructure as Code (Terraform)

Terraform is included as a **IaC demonstration**.
Shows automated, versioned environment definition, but **should not be run directly** — the system collects local metrics, making remote provisioning unnecessary.

Recommended real deployment is **build and push the Docker image** to DockerHub.

---

## 6. Webhook & Security

The Discord webhook is managed via **GitHub Secrets**, never exposed in code.
Tokens and access keys used in pipelines are defined exclusively in `Settings > Secrets and variables > Actions`.

---

## 7. Structure & Relevant Files

```
src/
  core/            # Collection and treatment logic
  exporter/        # HTTP and Prometheus exporters
  monitoring/      # Collection control and scheduling
  system/          # Utility functions
infra/
  promtail/        # Log configuration
  terraform/       # IaC definitions
tests/             # Automated tests
.github/workflows/ # CI/CD (build, lint, tests)
```

---

## 8. Current Limitations

- Host collection is not guaranteed in containers.
- Exporter depends on local JSONL reading.
- Endpoints lack authentication.
- Terraform and observability are for demonstration only.

---

## 9. Evidence & Artifacts

| Area | Evidence | Path |
|------|----------|------|
| CI | ![CI](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml/badge.svg) | `.github/workflows/ci.yml` |
| Coverage | ![Tests](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg) | `.github/workflows/tests-coverage.yml` |
| CD | ![CD](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml/badge.svg) | `.github/workflows/cd.yml` |
| Terraform | ![Terraform](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml/badge.svg) | `.github/workflows/terraform.yml` |
| Gitleaks | ![Gitleaks](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/gitleaks-scan.yml/badge.svg) | `.github/workflows/gitleaks-scan.yml` |
| Snyk | ![Snyk](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml) | `.github/workflows/snyk-scan.yml` |
| Trivy | ![Trivy](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml) | `.github/workflows/trivy-scan.yml` |

---

## Final Technical Note — `psutil` Collection Limit

The `psutil` module collects metrics only from the environment where the process is running.
In containers or isolated namespaces, these metrics represent only the container context, not the host system.

Thus, its use is suitable for local diagnostics or in-process monitoring.
For real observability, it is recommended to integrate **node_exporter** or **cadvisor**, ensuring access to host metrics without breaking isolation.

> **Future improvement:** include a dedicated intermediate agent for host collection, maintaining isolation and compatibility with distributed observability.
