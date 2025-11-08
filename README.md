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

## 📘 Visão Geral

Aplicação desenvolvida para **coleta e exposição de métricas locais de sistema em tempo real**, com foco em **automação, integração contínua e observabilidade**.
Escrita em **Python**, a aplicação coleta dados de **CPU, memória e processos**, exportando métricas para integração com **Prometheus** e **Grafana**.
O projeto tem caráter **didático e profissional**, servindo como ambiente de validação de boas práticas de automação e infraestrutura.

---

## 🧩 Arquitetura e Fluxo

1. **Integração Contínua (CI)**
   Executa testes, lint e validações de dependências em cada commit.
   Garante integridade antes da build.

2. **Testes e Cobertura (Coverage)**
   Mede abrangência dos testes automatizados para manter a qualidade do código.

3. **Entrega Contínua (CD)**
   Constrói e publica a imagem Docker automaticamente.
   Controla versões e validações pós-deploy.

4. **Automação de Segurança**
   - **Dependabot:** mantém dependências atualizadas.
   - **Gitleaks:** evita vazamento de segredos.
   - **Snyk:** detecta vulnerabilidades em pacotes.
   - **Trivy:** analisa vulnerabilidades nas imagens Docker.

5. **Infraestrutura como Código (IaC)**
   Terraform é utilizado para provisionamento **demonstrativo**, documentando a possibilidade de replicação do ambiente em nuvem, embora a execução principal ocorra localmente.

---

## ⚙️ Execução Local

```bash
# Clonar o repositório
git clone https://github.com/Jeferson681/infra-monitoring-system.git
cd infra-monitoring-system

# Construir e executar containers
docker-compose up --build

# Acessar métricas locais
http://localhost:8000/metrics
```

---

## 🧱 Estrutura de Diretórios

```
infra-monitoring-system/
│
├── src/                  # Código-fonte principal
├── tests/                # Testes automatizados
├── infra/                # Infraestrutura (alertmanager, promtail, prometheus, terraform)
│   └── terraform/        # Provisionamento demonstrativo (README_TERRAFORM.md, main.tf)
├── .github/workflows/    # Pipelines CI/CD
├── Dockerfile            # Imagem do container
├── docker-compose.yml    # Orquestração dos containers
└── README.md
```

---

## 🧰 Stack Técnica

- **Linguagem:** Python
- **Monitoramento:** Prometheus, Grafana
- **Orquestração:** Docker, Docker Compose
- **Infraestrutura:** Terraform
- **Pipeline:** GitHub Actions
- **Sistema Operacional:** Linux (WSL compatível)

---

## 🔐 Segurança e Conformidade

O projeto adota múltiplos validadores de segurança e automação para prevenção de falhas e vulnerabilidades:
- Gitleaks (segredos)
- Snyk (pacotes)
- Trivy (imagens)
- Dependabot (dependências)

Essas etapas são automatizadas nos pipelines e visíveis via badges no topo.

---

## 🏗️ Infraestrutura (Terraform)

Terraform foi incluído **como módulo de demonstração profissional**, destacando domínio de IaC.
Seu uso é **documentado, porém não executado** durante o CD, pois o programa depende de métricas locais do host.

📄 Documentação completa disponível em
[`infra/terraform/README_TERRAFORM.md`](./infra/terraform/README_TERRAFORM.md)

---

## 📎 Licença

Este projeto é de uso livre para fins educacionais e demonstrativos.
Distribuído sob a licença **MIT**.

---
