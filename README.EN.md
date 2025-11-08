# 🖥️ Infra Monitoring System

[![CI](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml)
[![CD](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml)
[![Coverage](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml)
[![Dependabot Updates](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates)
[![Gitleaks](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/gitleaks-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/gitleaks-scan.yml)
[![Snyk](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml)
[![Trivy](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml)
[![Terraform](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml)

---

## 📘 Overview

Application developed for **real-time local system metrics collection and exposure**, focused on **automation, continuous integration, and observability**.
Written in **Python**, the application collects **CPU, memory, and process** data, exporting metrics for integration with **Prometheus** and **Grafana**.
The project is both **didactic and professional**, serving as a validation environment for automation and infrastructure best practices.

---

## 🧩 Architecture & Flow

1. **Continuous Integration (CI)**
   Runs tests, lint, and dependency validations on every commit.
   Ensures integrity before build.

2. **Tests & Coverage**
   Measures automated test coverage to maintain code quality.

3. **Continuous Delivery (CD)**
   Automatically builds and publishes the Docker image.
   Controls versions and post-deploy validations.

4. **Security Automation**
   - **Dependabot:** keeps dependencies up to date.
   - **Gitleaks:** prevents secret leaks.
   - **Snyk:** detects package vulnerabilities.
   - **Trivy:** scans Docker images for vulnerabilities.

5. **Infrastructure as Code (IaC)**
   Terraform is used for **demonstrative provisioning**, documenting the possibility of replicating the environment in the cloud, although main execution occurs locally.

---

## ⚙️ Local Execution

```bash
# Clone the repository
git clone https://github.com/Jeferson681/infra-monitoring-system.git
cd infra-monitoring-system

# Build and run containers
docker-compose up --build

# Access local metrics
http://localhost:8000/metrics
```

---

## 🧱 Directory Structure

```
infra-monitoring-system/
│
├── src/                  # Main source code
├── tests/                # Automated tests
├── infra/                # Infrastructure (alertmanager, promtail, prometheus, terraform)
│   └── terraform/        # Demonstrative provisioning (README_TERRAFORM.md, main.tf)
├── .github/workflows/    # CI/CD pipelines
├── Dockerfile            # Container image
├── docker-compose.yml    # Container orchestration
└── README.md
```

---

## 🧰 Tech Stack

- **Language:** Python
- **Monitoring:** Prometheus, Grafana
- **Orchestration:** Docker, Docker Compose
- **Infrastructure:** Terraform
- **Pipeline:** GitHub Actions
- **Operating System:** Linux (WSL compatible)

---

## 🔐 Security & Compliance

The project adopts multiple security and automation validators to prevent failures and vulnerabilities:
- Gitleaks (secrets)
- Snyk (packages)
- Trivy (images)
- Dependabot (dependencies)

These steps are automated in the pipelines and visible via badges at the top.

---

## 🏗️ Infrastructure (Terraform)

Terraform is included **as a professional demonstration module**, highlighting IaC expertise.
Its use is **documented but not executed** during CD, as the program depends on local host metrics.

📄 Full documentation available at
[`infra/terraform/README_TERRAFORM.md`](./infra/terraform/README_TERRAFORM.md)

---

## 📎 License

This project is free to use for educational and demonstrative purposes.
Distributed under the **MIT** license.

---
