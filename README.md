# Infra Monitoring System

[![CI](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml)\
[![CD](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml)\
[![Coverage](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg)\
[![Dependabot](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates)\
[![TruffleHog Secrets
Scan](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trufflehog-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trufflehog-scan.yml)\
[![Snyk](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml)\
[![Trivy](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml)\
[![Terraform](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml)

------------------------------------------------------------------------

## Overview

Infra Monitoring System is an architectural-focused monitoring project
designed to demonstrate:

-   Clean separation of concerns\
-   Decoupled metric providers\
-   Observability integration\
-   CI/CD automation\
-   Security pipeline integration\
-   Infrastructure as Code practices

This repository evolved from an experimental host-based collector into a
structurally extensible monitoring foundation, prepared for integration
with mature observability tools.

It is a technical and architectural demonstration project, not a
production monitoring product.

------------------------------------------------------------------------

## Problem Context

The original goal was to provide a controlled target for:

-   CI/CD pipeline validation\
-   Security automation testing\
-   Observability tooling experimentation\
-   IaC demonstrations

Instead of depending on external infrastructure, the system provides its
own observable target, enabling deterministic evaluation and
architectural experimentation.

------------------------------------------------------------------------

## Architectural Summary

``` text
Metric Provider (Pluggable)
        ↓
Domain Layer
        ↓
Exporter Interface (HTTP)
        ↓
Prometheus → Grafana / Loki
```

Key architectural characteristics:

-   Provider abstraction (metric source is replaceable)
-   Domain isolated from infrastructure concerns
-   Clear separation between collection and exposure
-   Prepared for integration with external agents and real-world tools

The metric source layer can evolve independently without impacting
business logic.

------------------------------------------------------------------------

## Architecture Principles

-   Single Responsibility per layer\
-   Infrastructure isolated from domain\
-   Replaceable metric providers\
-   Testable core logic\
-   Pipeline-first engineering mindset

------------------------------------------------------------------------

## Main Stack

-   Python\
-   Docker / Docker Compose\
-   Prometheus, Grafana, Loki\
-   GitHub Actions\
-   Terraform (educational IaC demonstration)

------------------------------------------------------------------------

## How to Run (3 commands)

``` bash
git clone https://github.com/Jeferson681/infra-monitoring-system.git
cd infra-monitoring-system
docker compose -f docker/docker-compose.yml up --build
```

For a clear separation between **venv runs** (local Python) and
**Docker/Compose runs**, plus expected collector vs exporter flows, see:

docs/RUN.md

------------------------------------------------------------------------

## What This Project Demonstrates

-   Architectural evolution from experimental collector to extensible
    design\
-   Observability integration (metrics + logs)\
-   CI/CD pipelines with security automation\
-   Static analysis and dependency scanning\
-   IaC concepts separated from runtime logic\
-   Documentation organization and technical decision tracking

------------------------------------------------------------------------

## Technical Documentation

-   Documentation portal: docs/DOCS.md\
-   Technical deep-dive (EN - canonical): docs/README-TECH.md\
-   Technical decisions: docs/DECISIONS.md\
-   How to run: docs/RUN.md\
-   Visual evidence: docs/prints/README.md

------------------------------------------------------------------------

## Developer Setup (Local Checks)

### Pre-commit & Linters

Run:

``` bash
pre-commit run --all-files
```

This executes formatters, linters and security hooks.

`hadolint` runs in CI during image scans.\
To run locally, use the `hadolint/hadolint` Docker image or install it
natively.

------------------------------------------------------------------------

### Docker (Optional)

Docker is required only if you want:

-   The full Docker Compose observability stack\
-   Local container image validation\
-   Parity with CI security checks

CI runners execute Trivy scans, hadolint and other checks automatically.
