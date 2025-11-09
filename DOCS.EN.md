# Infra Monitoring System — Technical Documentation

## 1. Purpose and Context

This system was developed for practical study of **monitoring, automation, and continuous integration (CI/CD)**.
The project collects and exposes system metrics (CPU, memory, processes, network) in real time, as well as structured logs integrable with **Prometheus**, **Grafana**, and **Loki**.
Its goal is to demonstrate a complete and observable pipeline, combining **Infrastructure as Code (IaC)**, **security**, **containerization**, and **automated delivery**.

---

## 2. General Architecture

The system operates with two main containers:

- **monitoring-app** — runs the monitoring core (`main.py`), responsible for collecting, processing, and persisting metrics in JSONL format.
- **monitoring-metrics** — runs the HTTP exporter (`main_http.py`), which reads the JSONL and exposes metrics and logs via endpoints compatible with Prometheus and Loki.

Both share the `/logs` volume, ensuring Promtail can access `.log` and `.json` files recursively. The file `infra/promtail/promtail-config.yml` defines the default collection behavior for Loki.

> **Didactic note:** In production environments, host metrics collection should be performed locally or via a dedicated agent, not by internal monitoring containers.

---

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

---

## 4. Observability and Integration

The environment integrates Prometheus, Grafana, and Loki via containers declared in `docker-compose.yml` and Terraform modules (`infra/terraform/main.tf`). Environment variables and volumes should be reviewed to ensure path and permission alignment.

**Applied best practices:**
- Structured and standardized logs.
- Metrics exposed in native Prometheus format.
- Isolated containers with controlled volume sharing.
- End-to-end observable integration (collection → export → visualization).

## 4.1 Service Access

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Loki: http://localhost:3100

---

## 5. Infrastructure as Code (Terraform)

Terraform is included for educational purposes only. It demonstrates infrastructure as code (IaC) definition for provisioning containers and observability services. As the system collects metrics from the host where it runs, cloud execution (e.g., AWS/ECS) will result in container/VM metrics, not physical host metrics. The recommended real deployment is building and pushing the Docker image to DockerHub.

---

## 6. Webhook and Security

The Discord webhook is managed via GitHub Secrets, not exposed in code. Tokens and access keys used in pipelines are defined exclusively via secure environment (`Settings > Secrets and variables > Actions`).

---

## 7. Directory Structure

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

---

## 8. Current Limitations

- Physical host monitoring is not guaranteed in containerized execution.
- The exporter depends on local reading of JSONL files --- no cache or streaming API.
- The system does not implement authentication on endpoints.
- Terraform and observability are for demonstration, not production.

---

## 9. Evidências e Artefatos

| Área        | Evidência                                                                                                                                       | Caminho                                               |
|--------------|------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------|
| CI           | ![CI](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml/badge.svg)                                               | `.github/workflows/ci.yml`                            |
| Coverage     | ![Tests & Coverage](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg)                     | `.github/workflows/tests-coverage.yml`                |
| CD           | ![CD](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml/badge.svg)                                               | `.github/workflows/cd.yml`                            |
| Terraform    | ![Terraform](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml/badge.svg)                                 | `.github/workflows/terraform.yml`                     |
| Release      | ![Release](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/release.yml/badge.svg)                                     | `.github/workflows/release.yml`                       |
| Dependabot   | ![Dependabot Updates](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates/badge.svg)        | `.github/workflows/dependabot/dependabot-updates`     |
| Gitleaks     | ![Gitleaks](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/gitleaks-scan.yml/badge.svg)                              | `.github/workflows/gitleaks-scan.yml`                 |
| Snyk         | ![Snyk](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml/badge.svg)                                     | `.github/workflows/snyk-scan.yml`                     |
| Trivy        | ![Trivy](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml/badge.svg)                                   | `.github/workflows/trivy-scan.yml`                    |

**Recommended screenshots:**
- Successful CI pipeline execution.
- Grafana dashboard showing system metrics.
- Exporter returning data on `/health` and `/metrics` endpoints.

---

## 10. Final Technical Note

This project was developed for educational purposes and as a practical demonstration of best practices in development, automation, testing, and observability. The structure prioritizes modularity, traceability, and security, applying principles of continuous integration and validation in a controlled environment.

The source code is implemented in Python, focusing on clarity, testability, and separation of concerns. The infrastructure is defined in Terraform solely for educational purposes, illustrating concepts of automation and environment versioning, without active use during execution as it would affect local metric collection.

The pipelines automate the steps of linting, testing, coverage, build, and security analysis, ensuring consistency and continuous quality control. Tools like Gitleaks, Snyk, Trivy, and Dependabot provide preventive validation of vulnerabilities and dependencies.

Documentation follows the delivery cycle, prioritizing readability, technical review, and reproducibility of processes.

Last update: 09/11/2025
