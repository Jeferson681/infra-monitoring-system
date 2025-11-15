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

Aplicação para **coleta e exposição de métricas do sistema local**, criada para prática de desenvolvimento em Python e uso de ferramentas voltadas a automação, CI/CD e observabilidade.
As métricas são coletadas por meio da biblioteca **psutil**, que lê dados diretamente do host. Quando executada em contêineres, essa abordagem apresenta limitações naturais devido ao acesso reduzido ao sistema hospedeiro.
O projeto integra métricas, logs e visualizações utilizando a stack de observabilidade: Prometheus, Grafana e Loki, com execução organizada em contêineres para garantir reprodutibilidade, isolamento e facilidade de análise.

---

## 🖼️ Artefatos / Evidências

Uma seleção precisa de evidências visuais (diagramas, dashboards e capturas de execução). As imagens completas estão organizadas em uma galeria dedicada para visualização ordenada, sem sobrecarregar o corpo principal do README.

<div>
   <a href="docs/prints/README.md"><img src="docs/prints/architecture.png" alt="architecture" style="width:240px;margin-right:12px;border:1px solid #ddd"/></a>
   <a href="docs/prints/README.md"><img src="docs/prints/dashboard_panel_grafana.png" alt="grafana" style="width:240px;border:1px solid #ddd"/></a>
</div>

[Ver galeria completa →](docs/prints/README.md)

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
5. **Infraestrutura como Código (IaC)** — Terraform documenta a infraestrutura de forma declarativa, validada nos pipelines, mas sem provisionamento real.

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

**Observação:** o projeto expõe métricas diretamente no endpoint `/metrics` (exporter interno). Para métricas do host físico, utilize `node_exporter` ou `cadvisor`; `psutil` coleta apenas o contexto do processo/container.

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
- **Sistema Operacional:** Linux, WSL2 e Windows nativo

---

## 🔐 Segurança e Conformidade

- **Gitleaks** — previne exposição de segredos.
- **Snyk** — detecta vulnerabilidades.
- **Trivy** — escaneia imagens Docker.
- **Dependabot** — mantém dependências seguras e atualizadas.

Todas as verificações são automatizadas via pipelines GitHub Actions.

---

## 🏗️ Infraestrutura (Terraform)

O Terraform documenta a infraestrutura de forma declarativa e é usado neste projeto como módulo demonstrativo de IaC. O código é validado nos pipelines, mas não é aplicado automaticamente: as métricas coletadas referem-se ao ambiente local e o provisionamento em cloud não é necessário, o que evita custos não intencionais. Trechos do código e das pipelines relacionados ao provisionamento estão comentados ou configurados para não serem acionados automaticamente; podem ser habilitados futuramente mediante revisão, configuração de segredos e permissões apropriadas. A estrutura permanece disponível para consulta, revisão técnica e possível ativação controlada.

---

## 🧾 Nota Técnica Final — Limite de Coleta com psutil

O `psutil` coleta métricas do ambiente atual do processo.
Quando executado em containers, as métricas representam apenas o contexto do container, não do sistema hospedeiro.

Para observabilidade completa da infraestrutura, use **node_exporter** ou **cadvisor**.
O projeto utiliza psutil para coleta local e demonstra a integração com ferramentas de monitoramento dentro de um fluxo completo de automação.

---

## 📎 Licença

Distribuído sob a licença **MIT**.
Documentação completa disponível em [`/DOCS.md`](./DOCS.md).

---

## Evidências de Execução

As imagens contidas em `docs/prints/` registram a execução real do projeto no ambiente local, incluindo:

- Pipelines de CI em funcionamento.
- Execução de testes automatizados.
- Containers ativos via Docker Compose.
- Consultas e gráficos reais no Prometheus.
- Dashboards funcionais no Grafana.
- Logs coletados e processados via Loki.
- Estrutura de CD configurada, com seções comentadas para evitar acionamento não intencional.
- Arquivos Terraform validados conforme definido nos workflows.

Essas evidências confirmam a operação prática dos componentes apresentados na documentação.

---

## Considerações sobre Terraform

O Terraform está incluído para representar a definição declarativa da infraestrutura.
O código é validado, mas não aplicado, devido aos seguintes fatores:

- As métricas coletadas se referem ao ambiente local, não havendo necessidade de recursos externos.
- Evita-se criação de infraestrutura que possa gerar custos desnecessários.
- A estrutura permanece disponível para consulta e revisão técnica.

O material tem função demonstrativa e documenta o processo esperado em um fluxo de infraestrutura declarada.

---

## Estrutura de CD

A configuração de CD foi preparada para cenários de entrega controlada.
As seções comentadas mantêm a lógica visível e evitam acionamento indevido, garantindo:

- Segurança de execução.
- Clareza da estrutura existente.
- Possibilidade de ativação futura mediante configuração de permissões e segredos.

A lógica de entrega encontra-se pronta para uso quando necessário.

---

## CONTATOS

- Página pessoal: https://jeferson681.github.io/PAGE/
- Email: jefersonoliveiradesousa681@gmail.com
- LinkedIn: https://www.linkedin.com/in/jeferson-oliveira-de-sousa-ab8764164/

---
