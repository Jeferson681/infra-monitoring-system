# Decisões Técnicas

Este documento consolida as principais decisões técnicas e arquiteturais do projeto (dependências, formatos de dados e escolhas de integração).
As decisões estavam anteriormente distribuídas em múltiplos arquivos (`DOCS.md`, `README.md`, `infra/terraform/README_TERRAFORM.md`) e foram reunidas aqui para **facilitar revisão, manutenção e discussão técnica**. As referências originais permanecem listadas ao final.

---

## Decisões arquiteturais

- **Coleta host-aware com psutil**
	O projeto utiliza `psutil` para obter métricas do host (CPU, memória, disco e interfaces).
	**Racional:** coleta local direta, baixa dependência de agentes externos e compatibilidade multiplataforma.

- **Formato JSONL para exportação e arquivamento**
	O exportador gera e consome arquivos JSONL para persistência e replay de métricas/logs.
	**Racional:** suporte a streaming incremental, fácil ingestão por pipelines e boa aderência a testes de integração.

- **Ativação do exportador via variável de ambiente**
	A exposição de métricas é controlada por `MONITORING_EXPORTER_ENABLE=1`.
	**Racional:** habilitação explícita conforme ambiente (local, CI), evitando exposição acidental.

- **Persistência e replay de dados**
	Os dados persistidos ficam em `logs/json/` (ex.: `logs/json/monitoring-YYYY-MM-DD.jsonl`), sendo reutilizados pelo exportador para exposição de métricas.
	**Racional:** possibilita replay determinístico e validação em testes e pipelines.

---

## Decisões de integração

- **Arquitetura orientada à observabilidade (observability-first)**
	Integração planejada para exportador → Prometheus → Grafana, com Loki para logs.
	**Racional:** permite experimentação local via `docker-compose` e integração com stacks reais de observabilidade.

- **Terraform como demonstração de IaC**
	A pasta `infra/terraform` contém exemplos educacionais de infraestrutura.
	**Racional:** demonstrar conceitos de IaC sem tornar o Terraform parte do core do sistema ou da coleta de métricas.

---

## Critérios para mudanças futuras

- Qualquer mudança estrutural relevante (ex.: mover ou renomear arquivos de documentação) deve:
	1. Preservar backup em `docs/originals/`
	2. Atualizar links relativos afetados
	3. Executar verificação rápida (`pytest -q`) e checar endpoints do exportador

---

## Referências

- `DOCS.md`
- `README.md`
- `README_TERRAFORM.md` (quando aplicável)
 - `docs/diagrams/`
 - `prints/`

**Nota:** mantenha backups dos arquivos originais em `docs/originals/` antes de mover/renomear qualquer documento.
