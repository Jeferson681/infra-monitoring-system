# Infra Monitoring System

[![CI](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml) [![CD](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml) [![Coverage](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg) [![Dependabot](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates) [![TruffleHog Secrets Scan](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trufflehog-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trufflehog-scan.yml) [![Snyk](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml) [![Trivy](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml) [![Terraform](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml)

Educational target: a small, host-aware Python program for learning observability, testing CI/CD flows, and exercising DevOps tools in a controlled environment. This repository is intended as a teaching/demo artifact and not as a production DevOps product.

Problem it solves (learning context):

Provides a controlled target to practice and validate CI/CD pipelines, dashboards, and IaC demonstrations locally, avoiding external dependencies and simplifying technical evaluations.

Architecture (summary):

```text
Host
 ↓
Monitoring App (collection)
 ↓
Exporter (HTTP)
 ↓
Prometheus → Grafana / Loki
```

Main stack:

- Python
- Docker / Docker Compose
- Prometheus, Grafana, Loki
- GitHub Actions
- Terraform (demo)

How to run (3 commands):

```bash
git clone https://github.com/Jeferson681/infra-monitoring-system.git
cd infra-monitoring-system
docker compose -f docker/docker-compose.yml up --build
```

For a clear separation between **venv runs** (local Python) and **Docker/Compose runs**, plus the expected collector vs exporter flows, see [docs/RUN.md](docs/RUN.md).

What this project demonstrates:

- Host-aware collection with real metrics
- Integrated observability (metrics + logs)
- CI/CD pipelines and security automation
- Didactic IaC usage and documentation best practices

Technical documentation:

- 📚 Documentation portal: [docs/DOCS.md](docs/DOCS.md)
- 📘 Technical deep-dive (EN - canonical): [docs/README-TECH.md](docs/README-TECH.md)
- 🧠 Technical decisions: [docs/DECISIONS.md](docs/DECISIONS.md)
- ⚙️ How to run: [docs/RUN.md](docs/RUN.md)
- 🖼️ Visual evidence: [docs/prints/README.md](docs/prints/README.md)

## Developer setup (local checks)

- **Pre-commit & linters:** run `pre-commit run --all-files` to execute formatters, linters and security hooks. `hadolint` is executed in CI during image scans; to run it locally use the `hadolint/hadolint` Docker image or install `hadolint` natively.
- **Docker (optional):** Docker is only required for the Docker Compose local stack or for running some security tools locally (hadolint via Docker, TruffleHog). CI runners will execute image scans (Trivy) and hadolint with container images, so installing Docker locally is optional but recommended for full parity with CI.
