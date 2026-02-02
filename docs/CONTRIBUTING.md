# Contributing

Contact for questions, suggestions, or vulnerability reports: jefersonoliveiradesousa681@gmail.com

This document provides a simple checklist for reviewers and contributors.

## Quick reviewer guide

- Run local tests (smoke / unit):
  ```powershell
  pytest -q
  ```
- Run linters/formatters:
  ```powershell
  ruff src/ tests/
  flake8 src/ tests/
  black --check src/ tests/
  ```
- Run pre-commit hooks (optional):
  ```powershell
  pre-commit run --all-files
  ```
- Run TruffleHog locally before pushing (see `SECURITY.md`):
  ```powershell
  docker run --rm -v ${PWD}:/repo -w /repo trufflesecurity/trufflehog:latest filesystem /repo
  ```

## PR review checklist

1. CI is green (Actions: `CI / build-ubuntu`).
2. Coverage is reviewed for critical changes.
3. No secrets detected (TruffleHog).
4. Commit message and PR description are clear.
5. At least one approver reviewed the change.

## Pre-push checklist (run before commit/push)

- Run fast tests and linters:
  ```powershell
  pytest -q
  ruff src/ tests/
  flake8 src/ tests/
  pre-commit run --all-files
  ```
- Run TruffleHog locally to detect secrets:
  ```powershell
  docker run --rm -v ${PWD}:/repo -w /repo trufflesecurity/trufflehog:latest filesystem /repo
  ```

## Hadolint (local)

`hadolint` runs in CI during image scans. To run it locally, you can use the official image:

```powershell
docker run --rm -v ${PWD}:/data -w /data hadolint/hadolint:latest hadolint Dockerfile
```

Or install `hadolint` natively and run `hadolint Dockerfile`.

Smoke import test:

```powershell
python -c "import importlib; importlib.import_module('src'); print('import ok')"
```

## Discord webhook & tokens

The Discord webhook is managed via GitHub Actions Secrets (same idea as the CD workflow). Do not configure it manually and never commit tokens.

## Terraform

Terraform is a didactic placeholder in this repository and is not used for real provisioning. AWS credentials are not required.

## How to run locally (try-it quick)

1. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
2. Run tests:
   ```powershell
   pytest -q
   ```
3. Run via Docker Compose (alternative):
  ```powershell
 docker compose up --build
 # in another terminal:
 # Only reachable from the host if `ports:` is configured in docker-compose.yml; see docs/RUN.md
 curl http://localhost:8000/metrics
  ```

---

If you want to suggest improvements to the review process, open an issue with the `meta` tag.
