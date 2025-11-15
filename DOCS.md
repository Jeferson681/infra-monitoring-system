# Infra Monitoring System — Documentação Técnica

## 1. Propósito e Contexto

Este sistema foi desenvolvido com finalidade educacional e demonstração prática de boas práticas em monitoramento, automação e integração contínua.
Implementa coleta e exposição de métricas e logs enriquecidos, com integração às principais ferramentas de observabilidade: **Prometheus**, **Grafana** e **Loki**.

O foco é demonstrar o fluxo completo de **coleta → persistência → exportação → análise** em um ambiente automatizado, versionado e seguro.

---

## 2. Arquitetura Geral

O sistema opera em dois containers principais:

- **monitoring-app** — executa o núcleo de monitoramento (`main.py`), responsável por coleta, tratamento e gravação das métricas em formato JSONL.
- **monitoring-metrics** — executa o exporter HTTP (`main_http.py`), que lê o JSONL e expõe métricas e logs em endpoints compatíveis com Prometheus e Loki.

Ambos compartilham o volume `/logs`, garantindo que o Promtail acesse os arquivos `.log` e `.json`.
O arquivo `infra/promtail/promtail-config.yml` define o comportamento padrão de coleta para o Loki.

> **Observação técnica:** o container `monitoring-metrics` é demonstrativo. Em ambientes produtivos, a coleta deve ser feita localmente ou via agente dedicado, não em containers internos de monitoramento.

---

## 3. Fluxo de Métricas e Logs

### 3.1 Coleta e Persistência
O módulo principal coleta dados do sistema (CPU, memória, disco, rede e latência) e grava em JSONL rotativo.
Os logs são estruturados em JSON e armazenados no mesmo volume compartilhado.

### 3.2 Exportação
O exporter lê a última linha do JSONL e atualiza os *Gauges* de Prometheus, expondo apenas o snapshot atual.

**Endpoints disponíveis:**
- `/health`: resumo JSON das métricas.
- `/metrics`: formato Prometheus exposition (texto plano).

### 3.3 Métricas de Processo
Métricas do processo Python (CPU, memória, threads, uptime, descritores) são coletadas em tempo real e não persistidas.

> **Recomendação:** alinhar o `scrape_interval` do Prometheus ao intervalo de coleta do monitoramento.

---

## 4. Observabilidade e Integração

A integração ocorre via containers definidos no `docker-compose.yml` e módulos Terraform (`infra/terraform/main.tf`).
Variáveis de ambiente e volumes devem ser revisadas conforme o ambiente de execução.

**Boas práticas aplicadas:**
- Logs padronizados e estruturados.
- Métricas nativas Prometheus.
- Containers isolados com volumes controlados.
- Integração ponta a ponta (coleta → exportação → visualização).

**Acesso padrão:**
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Loki: http://localhost:3100

---

## 5. Infraestrutura como Código (Terraform)

O Terraform é incluído como demonstração de **IaC** (Infrastructure as Code).
Demonstra a definição de ambientes automatizados e versionados, mas **não deve ser executado diretamente** — o sistema coleta métricas locais, tornando desnecessário o provisionamento remoto.

O deploy real recomendado é o **build e push da imagem Docker** para o DockerHub.

---

## 6. Webhook e Segurança

O webhook do Discord é gerenciado via **GitHub Secrets**, sem exposição no código.
Tokens e chaves de acesso utilizados nos pipelines estão definidos exclusivamente em `Settings > Secrets and variables > Actions`.

---

## 7. Estrutura e Arquivos Relevantes

```
src/
  core/            # Lógica de coleta e tratamento
  exporter/        # Exportadores HTTP e Prometheus
  monitoring/      # Controle e agendamento de coletas
  system/          # Funções utilitárias
infra/
  promtail/        # Configuração de logs
  terraform/       # Definições IaC
tests/             # Testes automatizados
.github/workflows/ # CI/CD (build, lint, testes)
```

---

## 8. Limitações Atuais

- Coleta do host físico não é garantida em containers.
- Exporter depende de leitura local do JSONL.
- Endpoints sem autenticação.
- Terraform e observabilidade usados apenas para demonstração.

---

## 9. Evidências e Artefatos

| Área | Evidência | Caminho |
|------|------------|---------|
| CI | ![CI](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml/badge.svg) | `.github/workflows/ci.yml` |
| Coverage | ![Tests](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg) | `.github/workflows/tests-coverage.yml` |
| CD | ![CD](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml/badge.svg) | `.github/workflows/cd.yml` |
| Terraform | ![Terraform](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml/badge.svg) | `.github/workflows/terraform.yml` |
| Gitleaks | ![Gitleaks](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/gitleaks-scan.yml/badge.svg) | `.github/workflows/gitleaks-scan.yml` |
| Snyk | ![Snyk](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml/badge.svg) | `.github/workflows/snyk-scan.yml` |
| Trivy | ![Trivy](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml/badge.svg) | `.github/workflows/trivy-scan.yml` |

---

### Galeria de Artefatos

A galeria compacta com miniaturas está disponível abaixo; clique em qualquer imagem para abri-la em tamanho real. Se preferir, abra `docs/prints/README.md` para a mesma galeria embutida na pasta das imagens.

<table>
  <tr>
    <td align="center">
      <a href="docs/prints/architecture.png"><img src="docs/prints/architecture.png" alt="Architecture" style="width:320px;border:1px solid #ddd"/></a>
      <div><strong>Architecture</strong><br/><small>System components & flows</small></div>
    </td>
    <td align="center">
      <a href="docs/prints/flow_simple.png"><img src="docs/prints/flow_simple.png" alt="Flow" style="width:320px;border:1px solid #ddd"/></a>
      <div><strong>Simple Flow</strong><br/><small>High-level data flow</small></div>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="docs/prints/dashboard_panel_grafana.png"><img src="docs/prints/dashboard_panel_grafana.png" alt="Grafana" style="width:320px;border:1px solid #ddd"/></a>
      <div><strong>Grafana Dashboard</strong><br/><small>CPU / Memory / Disk panels</small></div>
    </td>
    <td align="center">
      <a href="docs/prints/dashboard_panel_grafana2.png"><img src="docs/prints/dashboard_panel_grafana2.png" alt="Grafana 2" style="width:320px;border:1px solid #ddd"/></a>
      <div><strong>Grafana Detail</strong><br/><small>Panel detail view</small></div>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="docs/prints/target_prometheus_up.png"><img src="docs/prints/target_prometheus_up.png" alt="Prometheus targets" style="width:320px;border:1px solid #ddd"/></a>
      <div><strong>Prometheus Targets</strong><br/><small>Targets UP</small></div>
    </td>
    <td align="center">
      <a href="docs/prints/prometheus_query_graph.png"><img src="docs/prints/prometheus_query_graph.png" alt="Prometheus graph" style="width:320px;border:1px solid #ddd"/></a>
      <div><strong>Prometheus Graph</strong><br/><small>Sample query result</small></div>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="docs/prints/grafana_explore_loki_logs.png"><img src="docs/prints/grafana_explore_loki_logs.png" alt="Grafana logs" style="width:320px;border:1px solid #ddd"/></a>
      <div><strong>Grafana Explore</strong><br/><small>Loki logs query</small></div>
    </td>
    <td align="center">
      <a href="docs/prints/promtail_logs_loki.png"><img src="docs/prints/promtail_logs_loki.png" alt="Promtail" style="width:320px;border:1px solid #ddd"/></a>
      <div><strong>Promtail Logs</strong><br/><small>Log shipping evidence</small></div>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="docs/prints/docker_compose_up.png"><img src="docs/prints/docker_compose_up.png" alt="Docker" style="width:320px;border:1px solid #ddd"/></a>
      <div><strong>Containers Running</strong><br/><small>docker compose ps</small></div>
    </td>
    <td align="center">
      <a href="docs/prints/infra_monitoring_terminal.png"><img src="docs/prints/infra_monitoring_terminal.png" alt="Terminal" style="width:320px;border:1px solid #ddd"/></a>
      <div><strong>Local Run</strong><br/><small>Exporter serving / health</small></div>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="docs/prints/GitHub_Actions.png"><img src="docs/prints/GitHub_Actions.png" alt="CI" style="width:320px;border:1px solid #ddd"/></a>
      <div><strong>CI Pipeline</strong><br/><small>GitHub Actions run</small></div>
    </td>
    <td/>
  </tr>
</table>


## Nota Técnica Final — Limite de Coleta com `psutil`

O módulo `psutil` coleta métricas apenas do ambiente em que o processo está em execução.
Em containers ou namespaces isolados, essas métricas representam apenas o contexto do container, não o sistema hospedeiro.

Assim, seu uso é adequado para diagnósticos locais ou monitoramento in-process.
Para observabilidade real, recomenda-se integrar **node_exporter** ou **cadvisor**, garantindo acesso às métricas do host físico sem violar isolamento.

> **Melhoria futura:** incluir agente intermediário dedicado à coleta do host, mantendo o isolamento e compatibilidade com observabilidade distribuída.

---

## CONTATOS

- Página pessoal: https://jeferson681.github.io/PAGE/
- Email: jefersonoliveiradesousa681@gmail.com
- LinkedIn: https://www.linkedin.com/in/jeferson-oliveira-de-sousa-ab8764164/

---
