PYTHON ?= python3
PIP ?= pip3

.PHONY: install dev worker test format compose-up compose-down help test-docker cov-docker

help:
	@echo "Targets: install, dev, worker, test, format, compose-up, compose-down, test-docker, cov-docker"

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

# Run tests inside docker api container (with migrations)
test-docker:
	docker compose up -d postgres redis api
	docker compose exec -T -e PYTHONPATH=/app api alembic upgrade head
	docker compose exec -T -e PYTHONPATH=/app api pytest -q

# Run coverage inside docker api container and export coverage.xml to host
cov-docker:
	docker compose up -d postgres redis api
	docker compose exec -T -e PYTHONPATH=/app api sh -lc 'python -m pip install --upgrade pip >/dev/null 2>&1 || true; pip install coverage >/dev/null 2>&1 || true; coverage run -m pytest && coverage xml && coverage report -m'
	@cid=$$(docker compose ps -q api); docker cp $$cid:/app/coverage.xml ./coverage.xml || true; echo "coverage.xml exported (if exists)"
