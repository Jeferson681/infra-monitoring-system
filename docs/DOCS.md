# Infra Monitoring System — Documentação Técnica

# Índice de documentação

Este arquivo foi consolidado. As versões canônicas da documentação técnica estão em:

- Português (canônico): [docs/README-TECH.md](README-TECH.md)
- English (canonical): [docs/README-TECH.EN.md](README-TECH.EN.md)

Backups das versões originais estão disponíveis em `docs/originals/` caso seja necessário restaurar conteúdo completo.

Use os arquivos canônicos para leitura detalhada, e abra issues/PRs se quiser consolidar ou reorganizar o material.

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
