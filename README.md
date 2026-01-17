# Infra Monitoring System

[![CI](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml) [![CD](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml) [![Coverage](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml) [![Dependabot](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates) [![Gitleaks](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/gitleaks-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/gitleaks-scan.yml) [![Snyk](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml) [![Trivy](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml) [![Terraform](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml)

Aplicação para coleta e exposição de métricas locais, focada em observabilidade e automação de práticas DevOps.

Problema que resolve:

Fornece um alvo controlado para testar e validar pipelines CI/CD, dashboards e demonstrações de IaC em ambiente local, evitando dependências externas e simplificando avaliações técnicas.

Arquitetura (resumo):

```text
Host
 ↓
Monitoring App (coleta)
 ↓
Exporter (HTTP)
 ↓
Prometheus → Grafana / Loki
```

Stack principal:

- Python
- Docker / Docker Compose
- Prometheus, Grafana, Loki
- GitHub Actions
- Terraform (demonstrativo)

Como rodar (3 comandos):

```bash
git clone https://github.com/Jeferson681/infra-monitoring-system.git
cd infra-monitoring-system
docker-compose up --build
```

O que este projeto demonstra:

- Coleta host-aware com métricas reais
- Observabilidade integrada (métricas + logs)
- Pipelines CI/CD e automação de segurança
- Uso didático de IaC e boas práticas de documentação

Documentação técnica:

- 📘 Documentação técnica: [docs/README-TECH.md](docs/README-TECH.md)
- 🧠 Decisões técnicas: [docs/DECISIONS.md](docs/DECISIONS.md)
- ⚙️ Como executar: [docs/RUN.md](docs/RUN.md)
- 🖼️ Evidências visuais: [docs/prints/README.md](docs/prints/README.md)
