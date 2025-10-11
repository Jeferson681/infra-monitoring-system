# DIRETRIZ DE AJUSTES DO PROJETO COM COPILOT
> Documento orientador para ajustes, modularização e documentação do projeto.
> Objetivo: finalizar o portfólio DevOps com consistência, sem perda de comportamento.

---

## ETAPA 0 — CONFIGURAÇÃO INICIAL

**Instruções para Copilot**
- Sempre preserve o comportamento atual do programa.
- Nunca altere nomes públicos de funções, classes ou módulos.
- Evite reescrever código que não esteja relacionado à solicitação.
- Use docstrings detalhadas e consistentes.
- Garanta compatibilidade entre módulos.
- Nenhum método deve executar I/O no import.
- Nomeie funções e variáveis de forma descritiva e contextual.

**Tarefas**
1. Ativar GitHub Copilot e Copilot Chat no VSCode.
2. Criar este arquivo `.copilot-instructions.md` na raiz do projeto.
3. Ler este documento antes de iniciar qualquer ajuste.

---

## ETAPA 1 — MAPEAMENTO DO PROJETO

**Prompt de comando**
```bash
@workspace liste todos os módulos e funções existentes e descreva o propósito de cada um em uma linha
```

**Checklist esperado**
- core
- settings
- averages
- metrics
- formatters
- state
- logs
- log_helpers
- handlers
- treatments
- main

---

## ETAPA 2 — DOCSTRINGS E TIPAGEM

**Prompt de comando**
```bash
@workspace adicione docstrings completas em todas as funções do módulo atual
@workspace adicione tipagem explícita em parâmetros e retornos
```

**Padrão da docstring**
- Descrição curta e direta.
- Parâmetros com tipo e descrição.
- Retornos e exceções documentados.
- Exemplo curto de uso (quando aplicável).

---

## ETAPA 3 — COMPLEXIDADE E REFINO

**Prompt de comando**
```bash
@workspace identifique funções com complexidade alta (C901)
@workspace proponha refatoração mínima mantendo comportamento e compatibilidade
```

**Regra**
- Funções acima de 50 linhas ou 3 blocos de lógica devem ser quebradas.
- Criar métodos auxiliares com prefixo `_` (internos).
- Cada função pública deve ter um único propósito.

---

## ETAPA 4 — MODULARIZAÇÃO CONTROLADA

**Prompt de comando**
```bash
@workspace separe funções longas em métodos auxiliares internos sem alterar nomes públicos
@workspace gere resumo de fluxo após refatoração
```

**Critério**
- Não mover funções entre módulos sem necessidade.
- Modularizar apenas quando houver ganho de clareza e testabilidade.

---

## ETAPA 5 — NORMALIZAÇÃO E FORMATTERS

**Prompt de comando**
```bash
@workspace identifique funções que fazem normalização ou formatação e centralize uso no módulo formatters
```

**Regra**
- Normalização ocorre dentro do módulo de origem.
- Formatação visual ou textual ocorre apenas no `formatters`.
- Nenhum dado cru deve ser impresso diretamente.

---

## ETAPA 6 — TRATAMENTO DE ESTADO E LOGS

**Prompt de comando**
```bash
@workspace valide o fluxo do módulo state.py garantindo um único snapshot principal e um único post_treatment
```

**Requisitos**
- Estados: stable, warning, critical, post_treatment.
- Cada evento gera apenas um log.
- O log deve ser tratado via `logs` e `log_helpers`.

---

## ETAPA 7 — TESTES UNITÁRIOS

**Prompt de comando**
```bash
@workspace gere stubs de testes unitários no diretório tests/
```

**Cobertura mínima**
- Métricas e thresholds.
- Máquina de estados (`state`).
- Escrita e rotação de logs.
- Normalização e formatação.

---

## ETAPA 8 — PADRONIZAÇÃO DE CÓDIGO

**Comandos para terminal**
```bash
black .
isort .
ruff --fix .
```

**Regra**
- Código deve passar sem erros C901 (complexidade) ou F401 (imports não usados).

---

## ETAPA 9 — DOCUMENTAÇÃO FINAL

**Prompt de comando**
```bash
@workspace gere README para cada módulo descrevendo:
Função principal, Fluxo interno e Exemplo prático
```

**Passos finais**
- Unir seções no README principal.
- Garantir coerência e clareza no fluxo geral.

---

## ETAPA 10 — FINALIZAÇÃO DO PORTFÓLIO

**Tarefas**
1. Criar `Dockerfile` e `requirements.txt`.
2. Configurar Prometheus e Grafana.
3. Adicionar badges no README (coverage, docker build, CI status).
4. Criar tag final:

```bash
git tag -a v1.0.0 -m "Versão estável do portfólio DevOps"
git push origin v1.0.0
```

---

## REGRAS DE CONDUTA DO COPILOT

- Não propor frameworks desnecessários.
- Não mudar interfaces públicas.
- Manter comentários e docstrings consistentes.
- Preferir clareza e coesão ao invés de otimização prematura.
- Todas as refatorações devem preservar compatibilidade.

---

## FINALIZAÇÃO

Ao concluir cada etapa, registrar o progresso em `progress_log.md` com:
- Nome da etapa
- Data
- Resumo da modificação
- Lista de módulos afetados
