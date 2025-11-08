# Infra Monitoring System

### Visão Geral
Aplicação desenvolvida para coleta e exposição de métricas de uso de sistema em tempo real, com objetivo de consolidar práticas de automação, integração contínua e observabilidade.
O código base foi construído em **Python**, permitindo mensuração de CPU, memória e processos, além da exportação estruturada para integração com ferramentas de monitoramento.
O projeto tem natureza **didática**, servindo como ambiente controlado para validação de pipelines, infraestrutura como código e orquestração de containers.

### Arquitetura e Fluxo
1. **Integração Contínua (CI):**
   Testes automáticos de sintaxe e validação de dependências.
   Cada commit aciona pipelines para garantir consistência do código antes da build.

2. **Entrega Contínua (CD):**
   Empacotamento automatizado em container Docker.
   Deploy controlado com versionamento de imagens e verificação pós-deploy.

3. **Infraestrutura Automatizada (IaC):**
   Definição e provisionamento do ambiente via **Terraform**, garantindo reprodutibilidade e isolamento da infraestrutura.

4. **Observabilidade:**
   Exportação de métricas da aplicação e do ambiente via endpoint configurável.
   Coleta e visualização integradas a **Prometheus** e **Grafana**, permitindo análise de desempenho e alertas operacionais.

5. **Containerização:**
   Uso de **Docker Compose** para orquestrar múltiplos containers do sistema, simplificando inicialização e testes locais.

### Execução
```bash
# Clonar o repositório
git clone <repo-url>

# Construir e executar containers
docker-compose up --build

# Acessar métricas locais
http://localhost:8000/metrics
```

### Ambiente e Ferramentas
- **Linguagem:** Python
- **Monitoramento:** Prometheus, Grafana
- **Orquestração:** Docker, Docker Compose
- **Infraestrutura:** Terraform
- **Pipeline:** GitHub Actions (CI/CD)
- **Sistema Operacional:** Linux (WSL compatível)

### Nota Técnica
O código foi desenvolvido com foco em aprendizado e validação prática de conceitos de automação, integração e infraestrutura escalável.
A aplicação principal serve como base funcional para experimentação de fluxos reais de deploy e monitoramento em ambiente controlado.

# Infra Monitoring System


[![CI](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml)
[![CD](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml)
[![Dependabot Updates](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates)
[![Gitleaks Secrets Scan](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/gitleaks-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/gitleaks-scan.yml)
[![Snyk Vulnerability Scan](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml)
[![Trivy Image Scan](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml)
[![Release](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/release.yml/badge.svg)](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/release.yml)
