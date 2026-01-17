# Arquitetura

Visão: este projeto é um exportador de monitoramento focado em observability-first — um coletor leve que transforma sinais locais em métricas e registros consumíveis por Prometheus/Grafana/Loki. O componente principal roda em processos Python (`src/`) e pode operar em fluxo local (venv) ou com `docker-compose` para experimentação end-to-end.

Limites: o exportador coleta métricas host-aware (via `psutil`) e consome/gera JSONL em `logs/json/` como forma de persistência e replay; ele não pretende ser um agente remoto universal. Integrações mais complexas (federation, long-term storage) ficam fora do escopo inicial e podem ser delegadas a infra externa (Prometheus remotos, object storage, etc.).

Componentes principais:
- Exporter (src): coleta e expõe métricas HTTP quando habilitado por ambiente.
- Persistência JSONL: `logs/json/` serve como fonte de ingestão/teste e como arquivo de transferência.
- Observability stack: Prometheus para scraping, Grafana para visualização e Loki para logs.
- Infra (opcional): `infra/terraform` contém exemplos educacionais de IaC para demonstração de deploy.

Evolução prevista: modularizar coletores (adicionar plugins), suportar autenticação e TLS, oferecer backend opcional para retenção longa, e adicionar testes de carga/integração. Ao mover/renomear artefatos visuais, mantenha arquivos em `prints/` e atualize links relativos.

Diagrama: veja `prints/architecture.png` para uma representação visual dos limites e fluxos.
