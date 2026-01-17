# Contato
Contato para dúvidas, sugestões ou reporte de vulnerabilidades: jefersonoliveiradesousa681@gmail.com

# Contributing

Obrigado por considerar contribuir com este projeto! Este arquivo traz um checklist simples para revisores e contribuidores.

## Guia rápido para revisores

- Rodar testes locais (smoke / unit):
  ```powershell
  pytest -q
  ```
- Rodar linters/formatadores:
  ```powershell
  ruff src/ tests/
  flake8 src/ tests/
  black --check src/ tests/
  ```
- Rodar pre-commit hooks (opcional):
  ```powershell
  pre-commit run --all-files
  ```
- Rodar Gitleaks local antes do push (ver `SECURITY.md`):
  ```powershell
  docker run --rm -v ${PWD}:/repo -w /repo zricethezav/gitleaks:latest detect --source /repo
  ```

## Checklist PR (revisor):

1. CI está verde (Actions: `CI / build-ubuntu`).
2. Cobertura (Codecov) revisada para alterações críticas.
3. Não há segredos detectados (Gitleaks).
4. Mensagem de commit/descritivo do PR clara.
5. Pelo menos 1 aprovador fez revisão.

## Pre-push checklist (execute antes de commitar/push)

- Rodar testes rápidos e linters:
  ```powershell
  pytest -q
  ruff src/ tests/
  flake8 src/ tests/
  pre-commit run --all-files
  ```
- Rodar Gitleaks local para detectar segredos:
  ```powershell
  docker run --rm -v ${PWD}:/repo -w /repo zricethezav/gitleaks:latest detect --source /repo
  ```
- Conferir Smoke import test:
  ```powershell
  python -c "import importlib; importlib.import_module('src'); print('import ok')"
  ```

## Webhook Discord e Tokens
O webhook do Discord é obtido automaticamente dos segredos do GitHub, igual ao workflow de CD. Não é necessário configurar manualmente. Todos os tokens e segredos já estão definidos via GitHub Secrets.

## Terraform
O Terraform permanece como placeholder didático e não será usado para provisionamento real. Credenciais AWS não são necessárias nem utilizadas neste projeto.

Adicione essas etapas ao fluxo de revisão para evitar falhas visíveis no CI e vazamento de segredos.

## Como rodar o projeto localmente (try-it quick)

1. Criar e ativar ambiente virtual:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
2. Rodar testes:
   ```powershell
   pytest -q
   ```
3. Rodar via Docker Compose (alternativa):
   ```powershell
   docker-compose up --build
   # em outro terminal:
   curl http://localhost:8000/metrics
   ```

---

Se quiser sugerir melhorias no processo de revisão, abra um issue com a tag `meta`.
