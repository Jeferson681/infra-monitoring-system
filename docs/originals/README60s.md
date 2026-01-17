````markdown
# Agente de Monitoramento de Host para Práticas DevOps

Agente local de coleta, tratamento e logs estruturados, utilizado como **alvo realista para práticas DevOps** (CI/CD, Observabilidade e IaC).

---

## O que é este projeto

Este projeto implementa um **agente de monitoramento host-aware** que executa diretamente no sistema operacional, coletando métricas do host, estruturando logs e expondo informações de saúde da aplicação.  
Ele foi projetado para servir como um **alvo real e controlado** para aplicar e validar práticas DevOps — **não** como uma ferramenta de infraestrutura ou plataforma de monitoramento.

---

## Problema que resolve

Projetos de aprendizado em DevOps frequentemente utilizam exemplos artificiais ou excessivamente simplificados.  
Este agente fornece um **sistema real executando no host**, permitindo aplicar pipelines de CI/CD, stacks de observabilidade, estratégias de testes e conceitos de infraestrutura como código em um contexto mais próximo do mundo real, com escopo e limitações claramente definidos.

---

## Arquitetura em alto nível

```
Sistema Host
 └─ Agente de Monitoramento (Python + psutil)
     ├─ Coleta de métricas do sistema
     ├─ Logs estruturados
     └─ Health checks
          ↓
     Prometheus / Grafana / Loki
          ↓
     Pipelines CI/CD • IaC (uso demonstrativo)
```

Um diagrama detalhado de arquitetura está disponível em `docs/prints/architecture.png`.

---

## Stack tecnológica

**Core**
- Python
- psutil
- Logs estruturados

**Observabilidade**
- Prometheus
- Grafana
- Loki

**DevOps**
- Docker / Docker Compose
- GitHub Actions
- Terraform (uso demonstrativo de IaC)

---

## Como executar (caminho principal)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

Para instruções de execução (local e Docker) veja `docs/RUN.md`. Para decisões técnicas (psutil, formato JSONL, ativação do exporter e integrações) veja `docs/DECISIONS.md`.

Métodos alternativos e documentação detalhada também estão em `docs/DOCS.md`.

---

## O que este projeto demonstra

- Design e manutenção de um **agente host-aware**, com decisões explícitas de arquitetura e uso de ferramentas
- Aplicação prática de **CI/CD, observabilidade, testes e conceitos de IaC** sobre um sistema real e manutenível

---

## Documentação técnica

A documentação técnica completa está disponível em [`docs/README.md`](docs/README.md), incluindo:
- Decisões arquiteturais e técnicas
- Configuração de observabilidade e dashboards
- Uso e escopo do Terraform
- Limitações do projeto e possibilidades de evolução

````
