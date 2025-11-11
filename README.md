# 🖥️ Infra Monitoring System

[![CI](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml)
[![CD](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml)
[![Coverage](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml)
[![Dependabot](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates)
[![Gitleaks](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/gitleaks-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/gitleaks-scan.yml)
[![Snyk](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml)
[![Trivy](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml)
[![Terraform](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml)

---

## 📘 Visão Geral

Aplicação profissional e educacional para **coleta e exposição de métricas de sistema local**, com foco em **automação, CI/CD e observabilidade**.
Desenvolvida em **Python**, integra métricas e logs ao ecossistema **Prometheus + Grafana + Loki**.

---

## 🧩 Arquitetura e Fluxo

1. **Integração Contínua (CI)** — valida código, dependências e testes.
2. **Cobertura de Testes (Coverage)** — mede abrangência de testes automatizados.
3. **Entrega Contínua (CD)** — constrói e publica a imagem Docker automaticamente.
4. **Automação de Segurança:**
   - Dependabot (dependências)
   - Gitleaks (segredos)
   - Snyk (vulnerabilidades de pacotes)
   - Trivy (análise de imagens)
5. **Infraestrutura como Código (IaC)** — Terraform documenta a automação de ambiente, **sem execução real** durante o CD.

---

## ⚙️ Execução Local

```shell
git clone https://github.com/Jeferson681/infra-monitoring-system.git
cd infra-monitoring-system
docker-compose up --build
```

**Serviços locais:**
- Prometheus → http://localhost:9090
- Grafana → http://localhost:3000
- Loki → http://localhost:3100
- Exporter → http://localhost:8000/metrics

Execução via virtualenv:

```shell
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Ativar exporter e iniciar monitoramento
export MONITORING_EXPORTER_ENABLE=1
export MONITORING_EXPORTER_ADDR=127.0.0.1
export MONITORING_EXPORTER_PORT=8000
python -m src.main -i 1 -c 0
```

---

## 🧱 Estrutura de Diretórios

```
infra-monitoring-system/
├── src/                  # Código-fonte principal
├── tests/                # Testes automatizados
├── infra/                # Configurações (promtail, terraform, prometheus)
│   └── terraform/        # IaC demonstrativo
├── .github/workflows/    # Pipelines CI/CD
├── Dockerfile            # Imagem Docker
├── docker-compose.yml    # Orquestração dos containers
└── README.md
```

---

## 🧰 Stack Técnica

- **Linguagem:** Python
- **Monitoramento:** Prometheus, Grafana, Loki
- **Orquestração:** Docker, Docker Compose
- **IaC:** Terraform
- **Pipeline:** GitHub Actions
- **Sistema Operacional:** Linux / WSL

---

## 🔐 Segurança e Conformidade

- **Gitleaks** — previne exposição de segredos.
- **Snyk** — detecta vulnerabilidades.
- **Trivy** — escaneia imagens Docker.
- **Dependabot** — mantém dependências seguras e atualizadas.

Todas as verificações são automatizadas via pipelines GitHub Actions.

---

## 🏗️ Infraestrutura (Terraform)

Terraform é usado como módulo **demonstrativo de IaC**, exibindo domínio conceitual e boas práticas de automação.
Como o sistema depende de métricas locais, **não executa provisionamento real em cloud**.

---

## 🧾 Nota Técnica Final — Limite de Coleta com psutil

O `psutil` coleta métricas do ambiente atual do processo.
Quando executado em containers, as métricas representam apenas o contexto do container, não do sistema hospedeiro.

Para observabilidade completa da infraestrutura, use **node_exporter** ou **cadvisor**.
Esta aplicação é voltada a fins didáticos e de validação de pipelines DevOps.

---

## 📎 Licença

Distribuído sob a licença **MIT**.
Documentação completa disponível em [`/DOCS.md`](./DOCS.md).
