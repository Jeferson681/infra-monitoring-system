# Infra Monitoring System

Alvo educacional: um pequeno programa Python host-aware para aprendizado em observabilidade, testes de pipelines CI/CD e exercícios de ferramentas DevOps em um ambiente controlado. Este repositório é destinado a ensino e demonstração, não a uso como produto DevOps de produção.

Problema que resolve (contexto de aprendizagem):

Fornece um alvo controlado para praticar e validar pipelines CI/CD, dashboards e demonstrações de IaC em ambiente local, evitando dependências externas e simplificando avaliações técnicas.

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
docker compose up --build
```

O que este projeto demonstra:

- Coleta host-aware com métricas reais
- Observabilidade integrada (métricas + logs)
- Pipelines CI/CD e automação de segurança
- Uso didático de IaC e boas práticas de documentação

Documentação técnica:

- 📚 Portal de documentação: [docs/DOCS.md](docs/DOCS.md)
- 📘 Documentação técnica (EN - canônico): [docs/README-TECH.md](docs/README-TECH.md)
- 📘 Documentação técnica (PT-BR): [docs/README-TECH.md](docs/README-TECH.md)
- 🧠 Decisões técnicas: [docs/DECISIONS.md](docs/DECISIONS.md)
- ⚙️ Como executar: [docs/RUN.md](docs/RUN.md)
- 🖼️ Evidências visuais: [docs/prints/README.md](docs/prints/README.md)

Setup do desenvolvedor (checks locais)

- **Pre-commit & linters:** execute `pre-commit run --all-files` para rodar formatadores, linters e hooks de segurança. O `hadolint` roda no CI durante os scans de imagem; para rodar localmente use a imagem Docker `hadolint/hadolint` ou instale o `hadolint` nativamente.
- **Docker (opcional):** Docker é necessário apenas para a stack local via Docker Compose ou para rodar algumas ferramentas de segurança localmente (hadolint via Docker, TruffleHog). Os runners de CI executam scans de imagem (Trivy) e hadolint com imagens de container, então instalar Docker localmente é opcional, mas recomendado para paridade total com o CI.
