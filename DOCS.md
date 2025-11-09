# Infra Monitoring System

## 1. Propósito e Contexto

Este sistema foi desenvolvido para fins de estudo prático de
monitoramento, automação e integração contínua. O código implementa
coleta e exposição de métricas do sistema e logs enriquecidos, com
integração a ferramentas padrão de observabilidade (Prometheus, Grafana,
Loki). O foco é demonstrar um fluxo completo de coleta, persistência,
exportação e análise de métricas em um ambiente automatizado e
versionado.

## 2. Arquitetura Geral

O sistema opera em dois containers principais: - **monitoring-app** ---
executa o núcleo de monitoramento (`main.py`), responsável por coleta,
tratamento e persistência das métricas em formato JSONL. -
**monitoring-metrics** --- executa o exporter HTTP (`main_http.py`), que
lê o JSONL e expõe métricas e logs via endpoints compatíveis com
Prometheus e Loki.

Ambos compartilham o volume `/logs`, garantindo que o Promtail acesse os
arquivos `.log` e `.json` de forma recursiva. O arquivo
`infra/promtail/promtail-config.yml` define o comportamento padrão de
coleta para o Loki.

**Observação didática:** o container `monitoring-metrics` tem função de
demonstração. Em ambientes reais, a coleta física do host deve ser feita
localmente ou via agente dedicado, não por containers de monitoramento
interno.

## 3. Fluxo de Métricas e Logs

### 3.1 Coleta e Persistência

O módulo principal coleta dados do sistema (CPU, memória, disco, rede,
latência) e grava em JSONL rotativo. Os logs são formatados em JSON
estruturado e armazenados no mesmo volume compartilhado.

### 3.2 Exportação

O exporter HTTP inicializa lendo a última linha do JSONL e atualiza os
*Gauges* de Prometheus. Nenhuma métrica é recalculada --- apenas o
último snapshot é exposto.

**Exporters:** - `/health`: retorna um resumo JSON de métricas do
sistema e processo. - `/metrics`: expõe os mesmos dados em formato
Prometheus exposition (texto plano).

### 3.3 Métricas de Processo

Métricas do processo Python (CPU, memória, threads, uptime, descritores)
são coletadas em tempo real. Essas métricas não são persistidas, apenas
expostas para observabilidade do container em execução.

**Recomendação:** alinhar o `scrape_interval` do Prometheus ao intervalo
de coleta definido no monitoramento para evitar inconsistências entre
snapshots.

## 4. Observabilidade e Integração

O ambiente integra Prometheus, Grafana e Loki por meio de containers
declarados no `docker-compose.yml` e módulos de Terraform
(`infra/terraform/main.tf`). As variáveis de ambiente e volumes devem
ser revisadas para garantir alinhamento de caminhos e permissões.

**Boas práticas aplicadas:** - Logs estruturados e padronizados. -
Métricas expostas em formato nativo Prometheus. - Containers isolados
com compartilhamento controlado de volumes. - Integração observável
ponta a ponta (coleta → exportação → visualização).

## 4.1 Acesso aos Serviços

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Loki: http://localhost:3100

## 5. Infraestrutura como Código (Terraform)

O Terraform está incluído somente com propósito educacional. Ele
demonstra definição de infraestrutura como código (IaC) para
provisionamento de containers e serviços de observabilidade. Como o
sistema coleta métricas do host onde é executado, a execução em cloud
(ex. AWS/ECS) resultará em métricas do container/VM, não do host físico.
O deploy real recomendado é o build e push da imagem Docker para o
DockerHub.

## 6. Webhook e Segurança

O webhook do Discord é gerenciado via GitHub Secrets, sem exposição no
código. Tokens e chaves de acesso utilizados nos pipelines são definidos
exclusivamente via ambiente seguro
(`Settings > Secrets and variables > Actions`).

## 7. Estrutura e Arquivos Relevantes

    src/
      core/            # Lógica de coleta e tratamento
      exporter/        # Exportadores Prometheus e HTTP
      monitoring/      # Controle e agendamento de coletas
      system/          # Funções utilitárias
    infra/
      promtail/        # Configuração de logs
      terraform/       # Definições IaC
    tests/             # Testes automatizados
    .github/workflows/ # CI/CD (build, lint, testes)

## 8. Limitações Atuais

-   O monitoramento do host físico não é garantido em execução
    containerizada.
-   O exporter depende de leitura local dos arquivos JSONL --- não há
    API de cache ou streaming.
-   O sistema não implementa autenticação nos endpoints.
-   Terraform e observabilidade servem para demonstração, não produção.

## 9. Evidências e Artefatos

| Área        | Evidência                                                                                                                                       | Caminho                                               |
|--------------|------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------|
| CI           | ![CI](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/ci.yml/badge.svg)                                               | `.github/workflows/ci.yml`                            |
| Coverage     | ![Tests & Coverage](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/tests-coverage.yml/badge.svg)                     | `.github/workflows/tests-coverage.yml`                |
| CD           | ![CD](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/cd.yml/badge.svg)                                               | `.github/workflows/cd.yml`                            |
| Terraform    | ![Terraform](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/terraform.yml/badge.svg)                                 | `.github/workflows/terraform.yml`                     |
| Release      | ![Release](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/release.yml/badge.svg)                                     | `.github/workflows/release.yml`                       |
| Dependabot   | ![Dependabot Updates](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/dependabot/dependabot-updates/badge.svg)        | `.github/workflows/dependabot/dependabot-updates`     |
| Gitleaks     | ![Gitleaks](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/gitleaks-scan.yml/badge.svg)                              | `.github/workflows/gitleaks-scan.yml`                 |
| Snyk         | ![Snyk](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/snyk-scan.yml/badge.svg)                                     | `.github/workflows/snyk-scan.yml`                     |
| Trivy        | ![Trivy](https://github.com/Jeferson681/infra-monitoring-system/actions/workflows/trivy-scan.yml/badge.svg)                                   | `.github/workflows/trivy-scan.yml`

**Screenshots recomendadas:** - Execução bem-sucedida do pipeline CI. -
Dashboard Grafana exibindo métricas do sistema. - Exporter retornando
dados nos endpoints `/health` e `/metrics`.

## 10. Nota Técnica Final

Este projeto foi desenvolvido com finalidade didática e demonstração prática de boas práticas em desenvolvimento, automação, testes e observabilidade. A estrutura prioriza modularidade, rastreabilidade e segurança, aplicando princípios de integração e validação contínuas em um ambiente controlado.

O código-fonte é implementado em Python, com foco em clareza, testabilidade e separação de responsabilidades. A infraestrutura foi definida em Terraform apenas com propósito educacional, servindo para ilustrar conceitos de automação e versionamento de ambiente, sem uso ativo durante a execução por afetar a coleta local de métricas.

Os pipelines automatizam as etapas de lint, testes, cobertura, build e análise de segurança, garantindo consistência e controle de qualidade contínuo. As ferramentas Gitleaks, Snyk, Trivy e Dependabot asseguram validação preventiva de vulnerabilidades e dependências.

A documentação acompanha o ciclo de entrega, priorizando legibilidade, revisão técnica e reprodutibilidade dos processos.

Última atualização: 09/11/2025
