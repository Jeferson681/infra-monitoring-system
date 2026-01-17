# Infra Monitoring System

---

## 📘 Visão Geral

Aplicação para **coleta e exposição de métricas do sistema local**, criada para prática de desenvolvimento em Python e uso de ferramentas voltadas a automação, CI/CD e observabilidade.

Principais decisões técnicas (coleta, formatos e integrações) e instruções de execução estão centralizadas em `docs/DECISIONS.md` e `docs/RUN.md`.

---

## 🖼️ Artefatos / Evidências

Uma seleção precisa de evidências visuais (diagramas, dashboards e capturas de execução). As imagens completas estão organizadas em uma galeria dedicada para visualização ordenada, sem sobrecarregar o corpo principal do README.

<div>
   <a href="prints/README.md"><img src="prints/architecture.png" alt="architecture" style="width:240px;margin-right:12px;border:1px solid #ddd"/></a>
   <a href="prints/README.md"><img src="prints/dashboard_panel_grafana.png" alt="grafana" style="width:240px;border:1px solid #ddd"/></a>
</div>

[Ver galeria completa →](prints/README.md)

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

# Consulte `docs/RUN.md` para instruções detalhadas de execução (variáveis de ambiente, Docker, Windows/Unix)

Nota rápida sobre exposição de métricas:

O projeto expõe métricas Prometheus em um único servidor HTTP (padrão `:8000`). Use `MONITORING_EXPORTER_ENABLE=1` para ativar o exporter (preferido). Existe um servidor HTTP de fallback que também pode expor `/metrics` quando necessário — habilite-o com `MONITORING_HTTP_ENABLE=1`, mas não use ambos simultaneamente para evitar conflito de portas. Detalhes em `docs/RUN.md`.
```

Para detalhes sobre ativação do exporter, limites de coleta via `psutil` e formato de persistência (JSONL), veja `docs/DECISIONS.md`.

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

---

Para detalhes sobre limites de coleta (`psutil`), persistência (JSONL) e ativação do exporter, consulte `docs/DECISIONS.md`. Instruções de execução estão em `docs/RUN.md`.

---

## 📎 Licença

Distribuído sob a licença **MIT**.
Documentação completa disponível em [`/DOCS.md`](./DOCS.md).

---

## Evidências de Execução

As imagens contidas em `prints/` registram a execução real do projeto no ambiente local, incluindo:

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
