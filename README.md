---

## 🧪 Testes

O projeto utiliza testes automatizados com `pytest` e validação de código com `pre-commit`.

### Rodando os testes

```sh
pytest
```

### Validando o código

```sh
pre-commit run --all-files
```

Consulte o arquivo `DOCS.md` para exemplos de cobertura, artefatos e recomendações de boas práticas.
---

## 🚢 Deploy

### Docker

O projeto pode ser executado via Docker usando o arquivo `docker-compose.yml`:

```sh
docker-compose up --build
```

Isso inicializa dois containers principais:
- `monitoring-app`: roda o monitoramento principal.
- `monitoring-metrics`: expõe endpoints de métricas e integra com Promtail/Loki.

### Terraform

O arquivo `infra/terraform/main.tf` demonstra como provisionar os containers usando Terraform. **Atenção:**
- O uso do Terraform neste projeto é apenas didático e não recomendado para produção, pois pode expor métricas do host de forma inadequada.
- Consulte o `DOCS.md` para recomendações e exemplos de arquitetura segura.
---

## ⚙️ Configuração de Ambiente

### Variáveis de Ambiente

- `MONITORING_EXPORTER_ENABLE`: Ativa o exporter Prometheus no programa principal (`main.py`). Use `0` para desativar e `1` para ativar.
- `MONITORING_HTTP_PORT`: Porta do serviço HTTP/Promtail (default: 8000).
- `LOKI_URL`: Endpoint do Loki para envio de logs (default: `http://loki:3100/api/prom/push`).
- `LOKI_LABELS`: Labels para logs enviados ao Loki (exemplo: `job=monitoring`).

### Volumes Compartilhados

- `/logs`: Diretório compartilhado entre containers para armazenamento e leitura de logs e arquivos JSON.
- `/.cache`: Diretório para controle de estado e arquivos temporários.

### Exemplo de Setup

No `docker-compose.yml`, os volumes e variáveis já estão configurados para garantir integração entre os serviços.

Consulte o arquivo `DOCS.md` para exemplos detalhados de configuração, recomendações e artefatos visuais.
---




# 📈 Monitoring System — Projeto Didático

<p align="right"><sub>Última atualização: 04/11/2025</sub></p>


## Sumário

- Stack: Python 3.13, pytest, ruff, flake8, black, bandit, Docker, Prometheus, Grafana, Terraform, Trivy
- Arquitetura: Modular, orientada a testes, observabilidade nativa, self-healing, logs estruturados, exportação Prometheus
- Pipelines automatizados e infraestrutura como código
- Documentação: Docstrings e comentários em português, código e logs em inglês, exemplos de integração e automação
- Projeto didático para aprendizado de Python, automação, testes e ferramentas de observabilidade

---

## 🚀 Instrução de Uso

### Instalação

1. Clone o repositório:
  ```sh
  git clone <url-do-repo>
  cd monitoring
  ```
2. Instale as dependências:
  ```sh
  pip install -r requirements.txt
  ```

### Execução

**Programa principal:**
```sh
python -m src.main
```

**Exporter HTTP/Promtail:**
```sh
python -m src.exporter.main_http
```

Consulte o arquivo `DOCS.md` para recomendações detalhadas, exemplos de configuração, artefatos, imagens e explicações sobre o funcionamento do sistema.

---

---

## 📝 Logs, Tratamentos e Coleta de Métricas

### Logs Estruturados e Rotacionáveis
- Todos os eventos relevantes (coleta, alertas, tratamentos, falhas) são registrados em logs estruturados (JSON e texto humano).
- Os logs são rotacionados e comprimidos automaticamente para evitar crescimento descontrolado.
- Logs incluem contexto de estado, timestamps e detalhes dos eventos/tratamentos.
- Funções principais: `write_log`, `rotate_logs`, `compress_old_logs`, `build_json_entry`.

### Tratamentos Automatizados (Self-Healing)
- O sistema detecta estados críticos (ex: uso excessivo de CPU, RAM, disco, falha de rede).
- Ao identificar um problema, dispara rotinas de tratamento específicas (ex: limpeza de arquivos temporários, reaplicação de configuração de rede, reaproveitamento de processos zumbis).
- Tratamentos são controlados por políticas de cooldown para evitar execuções repetidas.
- Resultados dos tratamentos são registrados e snapshots pós-tratamento são salvos para análise.
- Funções principais: `SystemState._activate_treatment`, `cleanup_temp_files`, `reap_zombie_processes`, `reapply_network_config`.

### Coleta de Métricas
- Métricas de CPU, memória, disco, rede, latência e temperatura são coletadas periodicamente.
- O sistema utiliza cache inteligente para evitar consultas excessivas e garantir performance.
- Fallbacks seguros garantem coleta mesmo em ambientes restritos.
- As métricas são avaliadas contra thresholds configuráveis para acionar alertas e tratamentos.
- Funções principais: `collect_metrics`, `compute_metric_states`, `SystemState.evaluate_metrics`.
# Monitoring

Sistema de monitoramento modular, extensível e orientado a boas práticas DevOps.


## ⚙️ Contexto e Fluxo do Programa

Este projeto foi desenvolvido com foco no aperfeiçoamento prático de **Python** e na aplicação dos **princípios fundamentais de DevOps**.
A arquitetura modular foi projetada para **estudo e experimentação de métricas, logs, pipelines e observabilidade**, simulando um ambiente real de monitoramento de sistemas.

Embora concebido como projeto de aprendizado, o sistema é totalmente funcional, podendo ser utilizado em **cenários pessoais ou laboratoriais** para coleta e análise contínua de métricas.

---

### 🧩 Fluxo Principal

1. **Inicialização (`main.py`)**
  - Faz parsing de argumentos e configura logging.
  - Inicializa arquivos de controle e tenta iniciar o exporter Prometheus (se ativado).
  - Chama o loop principal de monitoramento (`_run_loop`).

2. **Loop de Monitoramento (`core/core.py`)**
  - A cada ciclo:
    - Coleta métricas do sistema (`monitoring/metrics.py`).
    - Avalia estados e alertas (`monitoring/state.py`).
    - Emite snapshots (logs, arquivos, etc).
    - Executa rotinas de manutenção (rotação, compressão, limpeza de logs).

3. **Coleta de Métricas (`monitoring/metrics.py`)**
  - Coleta CPU, RAM, disco, rede, latência, temperatura, etc., com cache e fallback seguro.

4. **Gestão de Estado e Tratamentos (`monitoring/state.py`)**
  - Avalia métricas contra thresholds.
  - Dispara tratamentos automatizados (self-healing) em eventos críticos.
  - Registra snapshots pós-tratamento e mantém histórico.

5. **Logs e Manutenção (`system/logs.py`, `system/log_helpers.py`, `system/maintenance.py`)**
  - Gerenciam logs estruturados, rotação, compressão, escrita segura e manutenção periódica.

6. **Exportação de Métricas (`exporter/exporter.py`)**
  - (Opcional) expõe métricas para Prometheus via endpoint HTTP.

---

### 🔑 Funções e Classes Principais

- `main()`: inicializa e orquestra o ciclo de vida do monitor.
- `_run_loop()`: executa o ciclo de coleta, avaliação, emissão de snapshots e manutenção.
- `collect_metrics()`: coleta e normaliza métricas do sistema.
- `SystemState`: avalia estados, dispara tratamentos e mantém histórico.
- `emit_snapshot()`: registra e exporta snapshots do estado atual.

---

## 🔍 Funcionalidades Principais

- **Coleta e normalização de métricas** do sistema (CPU, memória, disco, rede).
- **Tratamentos automatizados (self-healing)** em eventos críticos, com execução controlada por políticas de cooldown.
- **Logs estruturados e rotacionáveis**, com contexto de estado e alertas ativos.
- **Cálculo de médias e tendências** via módulo *averages*, útil para detectar anomalias ou picos de uso.
- **Sistema de estados e alertas**, com níveis `stable`, `warning` e `critical`, além de snapshots pós-tratamento.
- **Fallback e tolerância a falhas** para garantir estabilidade em coleta e tratamento.
- **Observabilidade e exportação** planejadas via Prometheus e dashboards Grafana.
- **Integração com CI/CD e ferramentas de qualidade**, seguindo boas práticas DevSecOps.

---

## 🚀 Instalação e Execução

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
python -m src.main
```

---

## 🧪 Testes, Lint e Segurança

```bash
pytest
ruff src/ tests/
flake8 src/ tests/
black --check src/ tests/
bandit -r src/
```

---

## 🐳 Docker (em breve)

```bash
docker build -t monitoring .
docker run --rm -it monitoring
```

---

## 🌐 Endpoints Planejados

- `/health`: status do serviço
- `/metrics`: métricas Prometheus

---

## 📊 Observabilidade

- Exporters Prometheus planejados
- Integração com Grafana e dashboards

---

## 🔄 DevOps

- CI/CD com GitHub Actions
- Lint, testes, cobertura e análise de segurança automatizados
- Pronto para integração com Codecov, Trivy, Dependabot

---

# Badges

![CI](https://github.com/<usuario>/<repo>/actions/workflows/ci.yml/badge.svg)
![CD](https://github.com/<usuario>/<repo>/actions/workflows/cd.yml/badge.svg)
![Trivy](https://github.com/<usuario>/<repo>/actions/workflows/trivy-scan.yml/badge.svg)

# Fluxo CI/CD

- CI: Testes, lint, cobertura, segurança
- CD: Build/push Docker, deploy via SSH
- Trivy: Scan de imagem
- Dependabot: Atualização automática de dependências

# Observabilidade

- Prometheus scrape: `/metrics`
- Dashboard Grafana: pronto para importar

# Infraestrutura

- IaC: `infra/terraform/main.tf` (exemplo Docker)

# Como rodar local

```sh
# Build e subir stack
make build
make up
# Ou manualmente
# docker-compose up --build
```

# Variáveis e segredos

- Configure secrets do GitHub: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_KEY`

# Referências

- [Prometheus Exporter Python](https://github.com/prometheus/client_python)
- [Trivy](https://github.com/aquasecurity/trivy)
- [Terraform Docker Provider](https://registry.terraform.io/providers/kreuzwerker/docker/latest/docs)

---

> Substitua `<usuario>/<repo>` pelos dados do seu GitHub para ativar os badges.

---

## 🗂️ Estrutura do Projeto

```
src/        # Código-fonte principal
  config/   # Configurações
  core/     # Núcleo do sistema
  exporter/ # Exportação de métricas
  monitoring/ # Lógica de monitoramento
  system/   # Utilitários e integração
  ...
tests/      # Testes automatizados
.github/    # Workflows CI/CD
```

---

## 🤝 Contribuição
Pull requests são bem-vindos! Siga as boas práticas de código, testes e documentação.

## 📝 Licença
MIT
