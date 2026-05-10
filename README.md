# Infra Monitoring System

[![CI](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml)
[![Coverage](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml)
[![Security Scans](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml)
[![Terraform](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml)

---

## Overview

Infra Monitoring System is a study project focused on observability, operational automation and integration between monitoring tools.

The project provides a controlled environment for collecting metrics, visualizing data and validating CI/CD pipelines using Prometheus, Grafana, Loki and Docker Compose.

Instead of depending on external infrastructure, the system exposes its own observable target, allowing repeatable experiments and isolated testing scenarios.

This is a technical learning project and not a production monitoring platform.

---

## Main Goals

- Explore observability concepts in practice
- Validate CI/CD and security automation flows
- Experiment with Infrastructure as Code concepts
- Study integration between monitoring components
- Practice modular organization and infrastructure separation

---

## How the System Works

Simplified flow:

```text
Metric Provider
      ↓
Collection Layer
      ↓
HTTP Exporter
      ↓
Prometheus
      ↓
Grafana / Loki
```

The project separates metric collection from metric exposure, allowing the internal provider layer to evolve independently from the monitoring stack.

---

## Main Features

- Metrics collection using pluggable providers
- Prometheus integration for scraping metrics
- Grafana dashboards for visualization
- Loki integration for centralized logs
- Docker Compose environment for reproducible execution
- CI/CD pipelines with GitHub Actions
- Security and dependency scanning automation
- Terraform studies for Infrastructure as Code concepts

---

## Main Stack

- Python
- Docker / Docker Compose
- Prometheus
- Grafana
- Loki
- GitHub Actions
- Terraform

---

## Project Structure

```text
infra-monitoring-system/
├── docker/
├── docs/
├── scripts/
├── src/
├── tests/
└── .github/workflows/
```

Main areas:

- `src/` → application and metric collection logic
- `tests/` → automated tests
- `docker/` → observability stack configuration
- `docs/` → technical documentation and execution guides
- `.github/workflows/` → CI/CD and security pipelines

---

## Running the Project

```bash
git clone https://github.com/Jeferson681/infra-monitoring-system.git

cd infra-monitoring-system

docker compose -f docker/docker-compose.yml up --build
```

Detailed setup and environment information:

```text
docs/RUN.md
```

---

## CI/CD and Automation

The project includes automated pipelines for:

- tests execution
- linting and formatting
- dependency checks
- container security scanning
- Terraform validation

Main tools used:

- GitHub Actions
- Ruff
- pre-commit
- Trivy
- Snyk
- TruffleHog

---

## Technical Documentation

- `docs/DOCS.md`
- `docs/README-TECH.md`
- `docs/DECISIONS.md`
- `docs/RUN.md`
- `docs/prints/README.md`

---

## Purpose of the Project

This project was created as a practical environment for studying observability, automation and operational tooling integration.

The focus is on understanding system behavior, monitoring flows and infrastructure organization in a controlled and reproducible environment.
