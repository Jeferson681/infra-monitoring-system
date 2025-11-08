# Makefile para automação de tarefas comuns

.PHONY: lint test coverage build up down logs

lint:
	poetry run ruff src/ tests/
	poetry run black --check src/ tests/
	test -z "$(shell poetry run bandit -r src/ | grep 'No issues identified')" || exit 1

test:
	poetry run pytest

coverage:
	poetry run pytest --cov=src

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs
