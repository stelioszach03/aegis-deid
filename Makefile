PYTHON ?= python3
PIP ?= pip3

.PHONY: install dev worker test format compose-up compose-down help

help:
	@echo "Targets: install, dev, worker, test, format, compose-up, compose-down"

install:
	$(PIP) install -r requirements.txt

dev:
	uvicorn app.main:app --reload

worker:
	celery -A app.workers.celery_app.celery_app worker --loglevel=INFO

test:
	pytest -q

format:
	black . && ruff check --fix .

compose-up:
	docker compose up -d

compose-down:
	docker compose down
