# MAINTAINER_TODO

Entradas automáticas geradas pelo processo de padronização (Diretriz UNIVERSAL)

- 2025-10-06: `src/monitoring/averages.py` - marcada função `run_hourly_aggregation` com `# noqa: C901` devido à complexidade atual (muitos casos/formatos dependentes de leitura de JSONL). A refatoração deve ser feita com testes de integração; por ora mantido para evitar regressões. — responsável: jefer
