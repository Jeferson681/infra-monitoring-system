# Infra Monitoring System

---

## 📘 Overview

Application for **local system metrics collection and exposition**, designed to practice Python development and the use of automation, CI/CD, and observability tools.
Principles and operational details (collection, formats and integrations) are consolidated in `docs/DECISIONS.md`. Execution instructions are available in `docs/RUN.md`.

This file is the technical deep-dive:

- Focuses on architecture, runtime model, and operational choices.
- Not an audit report and not a mirror of the root `README.md`.
- Links out to decision logs and runbooks instead of duplicating them.

---

## 🖼️ Artifacts / Evidence

A compact selection of visual evidence (diagrams, dashboards and run captures). Full-size images are organized in a dedicated gallery so the main README stays concise and easy to scan.

<div>
   <a href="prints/README.md"><img src="prints/architecture.png" alt="architecture" style="width:240px;margin-right:12px;border:1px solid #ddd"/></a>
   <a href="prints/README.md"><img src="prints/dashboard_panel_grafana.png" alt="grafana" style="width:240px;border:1px solid #ddd"/></a>
</div>

[View full artifact gallery →](prints/README.md)

---

## 🧩 Architecture & Flow

1. **Continuous Integration (CI)** — validates code, dependencies, and tests.
2. **Test Coverage** — measures automated test coverage.
3. **Continuous Delivery (CD)** — builds and publishes the Docker image.
4. **Security Automation:**
   - Dependabot (dependencies)
   - TruffleHog (secrets)
   - Snyk (package vulnerabilities)
   - Trivy (image analysis)
5. **Infrastructure as Code (IaC)** — Terraform is included as an educational module and validated in CI, but not applied automatically.

Delivery posture (high-level): CD is designed for controlled activation. Steps that would require credentials/permissions can be gated or kept non-default, so the pipeline remains safe while still documenting the intended release flow.

---

## ⚙️ Local Execution

```shell
git clone https://github.com/Jeferson681/infra-monitoring-system.git
cd infra-monitoring-system
docker compose up --build
```

**Local services:**
- Prometheus → http://localhost:9090
- Grafana → http://localhost:3000
- Loki → http://localhost:3100
- Exporter → http://localhost:8000/metrics (only reachable from the host if `ports:` is published; see `docs/RUN.md`)

Run via virtualenv (see `docs/RUN.md` for platform-specific commands and exporter activation):

```shell
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Quick note on metrics exposure:

The project registers Prometheus metrics via the exporter (enable with `MONITORING_EXPORTER_ENABLE=1`). Serving the `/metrics` HTTP endpoint is a separate responsibility: in Compose the `main_http` service provides the scraped `/metrics` endpoint, and locally you can start the fallback HTTP server by setting `MONITORING_HTTP_ENABLE=1`. Enabling the exporter registers metrics; serving `/metrics` depends on either `main_http` (Compose) or the fallback HTTP server — do not enable both servers at the same time to avoid port bind conflicts. See `docs/RUN.md` for details and host reachability notes.

For exporter activation, limits of `psutil` and JSONL persistence details see `docs/DECISIONS.md`.

---

## 🏗️ Directory Structure

```
infra-monitoring-system/
├── src/                  # Main source code
├── tests/                # Automated tests
├── infra/                # Configurations (promtail, terraform, prometheus)
│   └── terraform/        # IaC demo
├── .github/workflows/    # CI/CD pipelines
├── Dockerfile            # Docker image
├── docker-compose.yml    # Container orchestration
└── README.md
```

---

## 🧑‍💻 Tech Stack

- **Language:** Python
- **Monitoring:** Prometheus, Grafana, Loki
- **Orchestration:** Docker, Docker Compose
- **IaC:** Terraform
- **Pipeline:** GitHub Actions
- **OS:** Linux, WSL2 and native Windows

---

## 🔒 Security & Compliance

- **TruffleHog** — prevents secret exposure.
- **Snyk** — detects vulnerabilities.
- **Trivy** — scans Docker images.
- **Dependabot** — keeps dependencies secure and up to date.

All checks are automated via GitHub Actions pipelines.

Webhook & secrets:

- The Discord webhook (when used) is managed via GitHub Actions Secrets and is never committed to the repository.
- Tokens and access keys used by pipelines should live under `Settings > Secrets and variables > Actions`.

---

## ⚠️ Known Limitations

- Host collection is not guaranteed in containers.
- The exporter depends on local JSONL persistence and exposes the latest snapshot.
- HTTP endpoints are unauthenticated (intended for local/demo use).

---

## 🏕️ Terraform (IaC demo)

Terraform is included as a didactic IaC module (see `infra/terraform/`).

- CI validates the configuration (format/lint/validate).
- It is intentionally not applied automatically.
- The goal is to document and review an expected declarative structure, not to provision real infra as part of local metrics collection.

If you want to adapt it for real environments, use an isolated account/workspace and review secrets/permissions first.

---

## 📎 License

Distributed under the **MIT** license.
Documentation portal available at [`/docs/DOCS.md`](./DOCS.md).
