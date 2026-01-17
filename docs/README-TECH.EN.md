# Infra Monitoring System

---

## 📘 Overview

Application for **local system metrics collection and exposition**, designed to practice Python development and the use of automation, CI/CD, and observability tools.
Principles and operational details (collection, formats and integrations) are consolidated in `docs/DECISIONS.md`. Execution instructions are available in `docs/RUN.md`.

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
3. **Continuous Delivery (CD)** — builds and publishes the Docker image automatically.
4. **Security Automation:**
   - Dependabot (dependencies)
   - Gitleaks (secrets)
   - Snyk (package vulnerabilities)
   - Trivy (image analysis)
5. **Infrastructure as Code (IaC)** — Terraform documents the infrastructure declaratively, validated in the pipelines, but without real provisioning.

---

## ⚙️ Local Execution

```shell
git clone https://github.com/Jeferson681/infra-monitoring-system.git
cd infra-monitoring-system
docker-compose up --build
```

**Local services:**
- Prometheus → http://localhost:9090
- Grafana → http://localhost:3000
- Loki → http://localhost:3100
- Exporter → http://localhost:8000/metrics

Run via virtualenv (see `docs/RUN.md` for platform-specific commands and exporter activation):

```shell
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

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

- **Gitleaks** — prevents secret exposure.
- **Snyk** — detects vulnerabilities.
- **Trivy** — scans Docker images.
- **Dependabot** — keeps dependencies secure and up to date.

All checks are automated via GitHub Actions pipelines.

---

## 🏕️ Infrastructure (Terraform)

The Terraform documents the infrastructure declaratively and is used in this project as a demonstrative IaC module. The configuration is validated in the pipelines but is not applied automatically: the metrics collected refer to the local environment and cloud provisioning is not necessary, which avoids unintended costs. Parts of the code and pipelines related to provisioning are commented or configured not to run automatically; they can be enabled later after review, secrets configuration and appropriate permissions. The structure remains available for inspection, technical review and controlled activation.

---

---

For technical details on `psutil` limits, JSONL persistence and exporter activation, see `docs/DECISIONS.md`. Run instructions are in `docs/RUN.md`.

---

## 📎 License

Distributed under the **MIT** license.
Full documentation available at [`/DOCS.EN.md`](./DOCS.EN.md).

Quick note on metrics exposure:

The project exposes Prometheus metrics via a single HTTP server (default `:8000`). Prefer enabling the exporter with `MONITORING_EXPORTER_ENABLE=1`. There is a fallback HTTP server that exposes `/health` and a fallback `/metrics` (enable with `MONITORING_HTTP_ENABLE=1`) — do not enable both at the same time to avoid port bind conflicts. See `docs/RUN.md` for details.

---

## Execution Evidence

The images available in `prints/` document the actual execution of the project in a local environment, including:

- CI pipelines running successfully.
- Automated test execution.
- Active containers through Docker Compose.
- Real Prometheus queries and graphs.
- Functional Grafana dashboards.
- Logs collected and processed by Loki.
- CD structure configured, with commented sections to prevent unintended execution.
- Terraform files validated according to the workflow configuration.

These records confirm the practical operation of all components described in the documentation.

---

## Terraform Considerations

Terraform is included to represent declarative infrastructure definition.
The configuration is validated but not applied, for the following reasons:

- Metrics collected refer to the local environment, making external resources unnecessary.
- Prevents the creation of infrastructure that could generate unintended costs.
- The structure remains available for inspection and technical review.

The material serves a demonstrative purpose, documenting the expected structure for declarative infrastructure.

---

## CD Structure

The CD configuration is prepared for controlled delivery scenarios.
Commented sections maintain visibility of the logic while preventing accidental execution, ensuring:

- Execution safety.
- Clarity of the existing configuration.
- Immediate activation capability when required, provided that secrets and permissions are configured.

The delivery logic is ready for activation whenever needed.

---

# CONTACTS

- Personal page: https://jeferson681.github.io/PAGE/
- Email: jefersonoliveiradesousa681@gmail.com
- LinkedIn: https://www.linkedin.com/in/jeferson-oliveira-de-sousa-ab8764164/

---
