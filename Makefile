# Makefile para automação de tarefas comuns

.PHONY: lint test coverage run run-main-http docker-build docker-up docker-down docker-logs

PY ?= python
COMPOSE ?= docker compose -f docker/docker-compose.yml

lint:
	$(PY) -m ruff check src tests
	$(PY) -m black --check src tests
	$(PY) -m bandit -r src

test:
	$(PY) -m pytest -q

coverage:
	$(PY) -m pytest --cov=src -q

# Minimal, predictable developer commands
run:
	$(PY) -m src.main

run-main-http:
	$(PY) -m infra_monitoring.api.exporter.main_http

docker-build:
	$(COMPOSE) build

docker-up:
	$(COMPOSE) up --build -d

docker-down:
	$(COMPOSE) down

docker-logs:
	$(COMPOSE) logs -f
