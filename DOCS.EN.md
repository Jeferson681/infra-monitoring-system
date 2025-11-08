# Infra Monitoring System — Technical Documentation  CI         ![CI](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml/badge.svg)          `.github/workflows/ci.yml`

  Lint       ![Lint](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/lint.yml/badge.svg)        `.github/workflows/lint.yml`

## 1. Purpose and Context  Tests      ![Tests & Coverage](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg) `.github/workflows/tests-coverage.yml`

  Terraform  ![Terraform](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml/badge.svg) `.github/workflows/terraform.yml`

System developed for educational purposes in **monitoring, automation, and continuous integration (CI/CD)**.    Release    ![Release](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/release.yml/badge.svg)  `.github/workflows/release.yml`

The project collects and exposes system metrics (CPU, memory, processes, network) in real time, as well as structured logs integrable with **Prometheus**, **Grafana**, and **Loki**.    Gitleaks   ![Gitleaks](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/gitleaks-scan.yml/badge.svg) `.github/workflows/gitleaks-scan.yml`

Its goal is to demonstrate a complete and observable pipeline, combining **Infrastructure as Code (IaC)**, **security**, **containerization**, and **automated delivery**.  Snyk       ![Snyk](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml/badge.svg)   `.github/workflows/snyk-scan.yml`

  Trivy      ![Trivy](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml/badge.svg) `.github/workflows/trivy-scan.yml`

---# Technical Documentation --- Infra Monitoring System



## 2. General Architecture## 1. Purpose and Context



The application operates with two main containers:This system was developed for practical study of monitoring, automation, and continuous integration. The code implements system metrics collection and enriched logs, integrating with standard observability tools (Prometheus, Grafana, Loki). The focus is to demonstrate a complete flow of collection, persistence, export, and analysis of metrics in an automated and versioned environment.



- **monitoring-app** — runs the core collector (`main.py`), responsible for capturing and writing metrics in JSONL.## 2. General Architecture

- **monitoring-metrics** — runs the HTTP exporter (`main_http.py`), which reads JSONL files and exposes metrics and logs via endpoints compatible with Prometheus and Loki.

The system operates in two main containers:

Both share the `/logs` volume, allowing recursive reading by tools like Promtail.- **monitoring-app** --- runs the monitoring core (`main.py`), responsible for collecting, processing, and persisting metrics in JSONL format.

- **monitoring-metrics** --- runs the HTTP exporter (`main_http.py`), which reads the JSONL and exposes metrics and logs via endpoints compatible with Prometheus and Loki.

> **Didactic note:** In production environments, host metrics collection should be performed locally or via an external agent, not inside monitoring containers.

Both share the `/logs` volume, ensuring Promtail can access `.log` and `.json` files recursively. The file `infra/promtail/promtail-config.yml` defines the default collection behavior for Loki.

---

**Didactic note:** The `monitoring-metrics` container is for demonstration. In real environments, host collection should be done locally or via a dedicated agent, not by internal monitoring containers.

## 3. Metrics and Logs Flow

## 3. Metrics and Logs Flow

### 3.1 Collection and Persistence

The main module collects data (CPU, RAM, disk, network, uptime, latency) and periodically writes to `.jsonl` files.  ### 3.1 Collection and Persistence

Structured JSON logs are saved in the same volume, facilitating tracking and analysis.

The main module collects system data (CPU, memory, disk, network, latency) and writes to rotating JSONL. Logs are formatted in structured JSON and stored in the same shared volume.

### 3.2 Export

The exporter reads the last line of the JSONL and updates *Gauges* exposed at:### 3.2 Export



- `/health` → state metrics in JSON.The HTTP exporter initializes by reading the last line of the JSONL and updates Prometheus *Gauges*. No metric is recalculated --- only the latest snapshot is exposed.

- `/metrics` → Prometheus format (plain text).

**Exporters:**

### 3.3 Process Metrics- `/health`: returns a JSON summary of system and process metrics.

Real-time collection of the active Python process (CPU usage, threads, descriptors, uptime).  - `/metrics`: exposes the same data in Prometheus exposition format (plain text).

These metrics are not persisted.

### 3.3 Process Metrics

**Recommendation:** Align Prometheus `scrape_interval` with the collection interval to avoid discrepancies.

Python process metrics (CPU, memory, threads, uptime, descriptors) are collected in real time. These metrics are not persisted, only exposed for container observability.

---

**Recommendation:** Align Prometheus `scrape_interval` with the monitoring collection interval to avoid inconsistencies between snapshots.

## 4. Observability and Integration

## 4. Observability and Integration

The environment integrates Prometheus, Grafana, and Loki via containers defined in `docker-compose.yml` and IaC (`infra/terraform/main.tf`).

The environment integrates Prometheus, Grafana, and Loki via containers declared in `docker-compose.yml` and Terraform modules (`infra/terraform/main.tf`). Environment variables and volumes should be reviewed to ensure path and permission alignment.

**Applied best practices:**

- Standardized and structured logs.  **Applied best practices:**

- Metrics compatible with Prometheus format.  - Structured and standardized logs.

- Isolated containers and controlled volumes.  - Metrics exposed in native Prometheus format.

- End-to-end observability (*collection → exposure → visualization*).- Isolated containers with controlled volume sharing.

- End-to-end observable integration (collection → export → visualization).

---

## 5. Infrastructure as Code (Terraform)

## 5. Infrastructure as Code (IaC)

Terraform is included for educational purposes only. It demonstrates infrastructure as code (IaC) definition for provisioning containers and observability services. As the system collects metrics from the host where it runs, cloud execution (e.g., AWS/ECS) will result in container/VM metrics, not physical host metrics. The recommended real deployment is building and pushing the Docker image to DockerHub.

**Terraform** is included only to demonstrate IaC practices.

Its purpose is to illustrate versioned infrastructure definition.  ## 6. Webhook and Security

Since the system collects host metrics, cloud execution (ECS, EC2, etc.) would only reflect container usage, not the physical machine.

The practical use indicated is **building and publishing the Docker image** to Docker Hub.The Discord webhook is managed via GitHub Secrets, not exposed in code. Tokens and access keys used in pipelines are defined exclusively via secure environment (`Settings > Secrets and variables > Actions`).



---## 7. Structure and Relevant Files



## 6. Webhook and Security    src/

      core/            # Collection and processing logic

The **Discord** webhook is configured via **GitHub Secrets**, with no exposure in the source code.        exporter/        # Prometheus and HTTP exporters

All keys and tokens used in pipelines are managed exclusively in:      monitoring/      # Collection control and scheduling

Settings → Secrets and Variables → Actions      system/          # Utility functions

    infra/

---      promtail/        # Log configuration

      terraform/       # IaC definitions

## 7. Directory Structure    tests/             # Automated tests

    .github/workflows/ # CI/CD (build, lint, tests)

src/

core/ # Main collection and processing logic## 8. Current Limitations

exporter/ # HTTP and Prometheus exporters

monitoring/ # Scheduling and execution control-   Physical host monitoring is not guaranteed in containerized execution.

system/ # Auxiliary and utility functions-   The exporter depends on local reading of JSONL files --- no cache or streaming API.

-   The system does not implement authentication on endpoints.

infra/-   Terraform and observability are for demonstration, not production.

promtail/ # Log configuration for Loki

terraform/ # IaC definitions (demonstration)## 9. Evidence and Artifacts



tests/ # Automated tests  Area       Evidence                              Path

.github/workflows/ # CI/CD pipelines and scanners  ---------- -------------------------------------- ----------------------------

  CI         ![CI Status](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml/badge.svg)          `.github/workflows/ci.yml`

---    Coverage   ![Coverage](https://codecov.io/gh/Jeferson681/infra-monitoring-system/branch/master/graph/badge.svg)     `tests/`

    Docker     ![Docker Build](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml/badge.svg)   `Dockerfile`

## 8. Current Limitations  Coverage   ![Coverage](https://codecov.io/gh/Jeferson681/infra-monitoring-system/branch/master/graph/badge.svg)     `tests/`

  Docker     ![Docker Build](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml/badge.svg)   `Dockerfile`

- Real host collection not guaranteed in containerized environments.    Dependabot ![Dependabot Updates](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates/badge.svg) `.github/workflows/dependabot/dependabot-updates`

- Exporter depends on local reading of `.jsonl` files.    Gitleaks   ![Gitleaks Secrets Scan](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/gitleaks-scan.yml/badge.svg) `.github/workflows/gitleaks-scan.yml`

- Endpoints have no authentication.    Snyk       ![Snyk Vulnerability Scan](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml/badge.svg) `.github/workflows/snyk-scan.yml`

- Terraform and observability are for demonstration only.  Trivy      ![Trivy Image Scan](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml/badge.svg) `.github/workflows/trivy-scan.yml`

  Release    ![Release](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/release.yml/badge.svg) `.github/workflows/release.yml`

---

**Recommended screenshots:**

## 9. Pipelines and Evidence- Successful CI pipeline execution.

- Grafana dashboard showing system metrics.

| Area        | Badge | Path |- Exporter returning data on `/health` and `/metrics` endpoints.

|--------------|--------|---------|

| **CI**        | ![CI](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml/badge.svg) | `.github/workflows/ci.yml` |## 10. Final Technical Note

| **Lint**      | ![Lint](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/lint.yml/badge.svg) | `.github/workflows/lint.yml` |

| **Tests & Coverage** | ![Coverage](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg) | `.github/workflows/tests-coverage.yml` |This project was developed for didactic purposes and practical demonstration of automation, observability, and continuous integration concepts. It does not replace corporate monitoring solutions. The focus is on applying best practices in structure, modularity, versioning, and automation with clean and documented code.

| **Terraform** | ![Terraform](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml/badge.svg) | `.github/workflows/terraform.yml` |

| **Release**   | ![Release](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/release.yml/badge.svg) | `.github/workflows/release.yml` |Last update: 2025-10-14

| **Gitleaks**  | ![Gitleaks](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/gitleaks-scan.yml/badge.svg) | `.github/workflows/gitleaks-scan.yml` |
| **Snyk**      | ![Snyk](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml/badge.svg) | `.github/workflows/snyk-scan.yml` |
| **Trivy**     | ![Trivy](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml/badge.svg) | `.github/workflows/trivy-scan.yml` |

**Visual evidence recommendations:**
- Complete execution of the CI/CD pipeline.
- Grafana dashboard with active metrics.
- Exporter returning `/health` and `/metrics`.

---

## 10. Final Technical Note

This project demonstrates the practical application of modern **observability** and **continuous integration** concepts.
It is not intended for production, but rather to showcase technical knowledge and best practices in development and automation.

**Last update:** 06/11/2025
