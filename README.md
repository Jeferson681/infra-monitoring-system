# Infra Monitoring System

[![CI](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml)\
[![CD](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml)\
[![Coverage](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg)\
[![Dependabot](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates)\
[![TruffleHog Secrets Scan](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trufflehog-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trufflehog-scan.yml)\
[![Snyk](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml)\
[![Trivy](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml)\
[![Terraform](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml)

---

## Overview

Infra Monitoring System is an architectural monitoring project designed as a controlled environment for:

- Observability tooling (Prometheus, Grafana, Loki)
- CI/CD and security pipeline validation
- Infrastructure as Code experimentation

The system intentionally avoids external dependencies by providing its own observable target, enabling deterministic testing and architectural evolution.

This is a technical demonstration project, not a production monitoring system.

---

## Problem Context

Instead of relying on external infrastructure, this project provides an internal observable system to:

- validate CI/CD pipelines
- test security automation
- experiment with observability tools
- demonstrate IaC practices

This allows full control over system behavior and repeatable experiments.

---

## Architectural Summary

    Metric Provider (Pluggable)
            ↓
    Domain Layer
            ↓
    Exporter Interface (HTTP)
            ↓
    Prometheus → Grafana / Loki

### Key Characteristics

- Provider abstraction (metric source is replaceable)
- Domain isolated from infrastructure concerns
- Clear separation between collection and exposure
- Prepared for integration with external tools

The metric source layer can evolve independently without impacting business logic.

---

## Key Principles

- Clear separation between domain and infrastructure
- Replaceable metric providers
- Testable core logic
- Pipeline-first engineering approach

---

## Main Stack

- Python
- Docker / Docker Compose
- Prometheus, Grafana, Loki
- GitHub Actions
- Terraform (educational IaC demonstration)

---

## How to Run

    git clone https://github.com/Jeferson681/infra-monitoring-system.git
    cd infra-monitoring-system
    docker compose -f docker/docker-compose.yml up --build

For environment separation (local vs Docker) and execution flow details:

`docs/RUN.md`

---

## What This Project Demonstrates

- Evolution from experimental collector to extensible architecture
- Observability integration (metrics and logs)
- CI/CD pipelines with security automation
- Static analysis and dependency scanning
- IaC concepts decoupled from runtime logic
- Structured technical documentation and decision tracking

---

## Technical Documentation

- Documentation portal: `docs/DOCS.md`
- Technical deep-dive (EN): `docs/README-TECH.md`
- Technical decisions: `docs/DECISIONS.md`
- Execution guide: `docs/RUN.md`
- Visual evidence: `docs/prints/README.md`

---

## Developer Setup (Local Checks)

### Pre-commit & Linters

    pre-commit run --all-files

Executes formatters, linters and security hooks.

`hadolint` runs in CI during image scans.
To run locally, use the `hadolint/hadolint` Docker image or install it natively.

---

## Docker (Optional)

Docker is required only for:

- Full observability stack via Docker Compose
- Local container validation
- CI parity (security checks)

CI pipelines include:

- Trivy (image scanning)
- hadolint (Dockerfile linting)
