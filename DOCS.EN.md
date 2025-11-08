# Technical Documentation --- Infra Monitoring System

## 1. Purpose and Context

This system was developed for practical study of monitoring, automation, and continuous integration. The code implements system metrics collection and enriched logs, integrating with standard observability tools (Prometheus, Grafana, Loki). The focus is to demonstrate a complete flow of collection, persistence, export, and analysis of metrics in an automated and versioned environment.

## 2. General Architecture

The system operates in two main containers:
- **monitoring-app** --- runs the monitoring core (`main.py`), responsible for collecting, processing, and persisting metrics in JSONL format.
- **monitoring-metrics** --- runs the HTTP exporter (`main_http.py`), which reads the JSONL and exposes metrics and logs via endpoints compatible with Prometheus and Loki.

Both share the `/logs` volume, ensuring Promtail can access `.log` and `.json` files recursively. The file `infra/promtail/promtail-config.yml` defines the default collection behavior for Loki.

**Didactic note:** The `monitoring-metrics` container is for demonstration. In real environments, host collection should be done locally or via a dedicated agent, not by internal monitoring containers.

## 3. Metrics and Logs Flow

### 3.1 Collection and Persistence

The main module collects system data (CPU, memory, disk, network, latency) and writes to rotating JSONL. Logs are formatted in structured JSON and stored in the same shared volume.

### 3.2 Export

The HTTP exporter initializes by reading the last line of the JSONL and updates Prometheus *Gauges*. No metric is recalculated --- only the latest snapshot is exposed.

**Exporters:**
- `/health`: returns a JSON summary of system and process metrics.
- `/metrics`: exposes the same data in Prometheus exposition format (plain text).

### 3.3 Process Metrics

Python process metrics (CPU, memory, threads, uptime, descriptors) are collected in real time. These metrics are not persisted, only exposed for container observability.

**Recommendation:** Align Prometheus `scrape_interval` with the monitoring collection interval to avoid inconsistencies between snapshots.

## 4. Observability and Integration

The environment integrates Prometheus, Grafana, and Loki via containers declared in `docker-compose.yml` and Terraform modules (`infra/terraform/main.tf`). Environment variables and volumes should be reviewed to ensure path and permission alignment.

**Applied best practices:**
- Structured and standardized logs.
- Metrics exposed in native Prometheus format.
- Isolated containers with controlled volume sharing.
- End-to-end observable integration (collection → export → visualization).

## 5. Infrastructure as Code (Terraform)

Terraform is included for educational purposes only. It demonstrates infrastructure as code (IaC) definition for provisioning containers and observability services. As the system collects metrics from the host where it runs, cloud execution (e.g., AWS/ECS) will result in container/VM metrics, not physical host metrics. The recommended real deployment is building and pushing the Docker image to DockerHub.

## 6. Webhook and Security

The Discord webhook is managed via GitHub Secrets, not exposed in code. Tokens and access keys used in pipelines are defined exclusively via secure environment (`Settings > Secrets and variables > Actions`).

## 7. Structure and Relevant Files

    src/
      core/            # Collection and processing logic
      exporter/        # Prometheus and HTTP exporters
      monitoring/      # Collection control and scheduling
      system/          # Utility functions
    infra/
      promtail/        # Log configuration
      terraform/       # IaC definitions
    tests/             # Automated tests
    .github/workflows/ # CI/CD (build, lint, tests)

## 8. Current Limitations

-   Physical host monitoring is not guaranteed in containerized execution.
-   The exporter depends on local reading of JSONL files --- no cache or streaming API.
-   The system does not implement authentication on endpoints.
-   Terraform and observability are for demonstration, not production.

## 9. Evidence and Artifacts

  Area       Evidence                              Path
  ---------- -------------------------------------- ----------------------------
  CI         ![CI Status](URL_DO_BADGE_CI)          `.github/workflows/ci.yml`
  Coverage   ![Coverage](URL_DO_BADGE_COVERAGE)     `tests/`
  Docker     ![Docker Build](URL_DO_BADGE_DOCKER)   `Dockerfile`

**Recommended screenshots:**
- Successful CI pipeline execution.
- Grafana dashboard showing system metrics.
- Exporter returning data on `/health` and `/metrics` endpoints.

## 10. Final Technical Note

This project was developed for didactic purposes and practical demonstration of automation, observability, and continuous integration concepts. It does not replace corporate monitoring solutions. The focus is on applying best practices in structure, modularity, versioning, and automation with clean and documented code.

Last update: 2025-10-14
