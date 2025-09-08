# Aegis De‑ID — PHI/PII De‑Identification MVP (EL/EN)

GDPR/HIPAA‑minded text de‑identification for English and Greek: detect PHI/PII and transform it (mask/hash/redact) via a simple API and UI.

[![CI](https://img.shields.io/github/actions/workflow/status/OWNER/REPO/ci.yml?label=CI)](./.github/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-%E2%89%A585%25-brightgreen.svg)](#testing--coverage)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Docker image size](https://img.shields.io/badge/docker-~300MB-informational.svg)](#quickstart)


## Screenshots (placeholders)

- UI Home (dark)

  ![UI Home Dark](docs/screenshots/ui_home_dark.png)

- Before → After (de‑identification)

  ![Before After](docs/screenshots/before_after.png)

- Entities & Filters (light)

  ![Entities Filters Light](docs/screenshots/entities_filters_light.png)


## Quickstart

Preferred: Docker Compose

```bash
# 1) Bring services up (API, worker, Redis, Postgres)
docker compose up -d --build

# 2) Apply DB migrations
docker compose exec -T api alembic upgrade head

# 3) Open UI
open http://localhost:8000  # or just visit in your browser
```

Local (venv)

```bash
# 1) Setup venv + deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Optional: spaCy models (best effort)
python -m spacy download en_core_web_sm || true
python -m spacy download el_core_news_sm || true

# 2) Migrations (requires local Postgres)
alembic upgrade head

# 3) Run API
uvicorn app.main:app --reload
# Optional worker
celery -A app.workers.celery_app.celery_app worker --loglevel=INFO
```

Environment

- Copy `.env.example` to `.env` and adjust.
- Key variables: `POSTGRES_DSN`, `REDIS_URL`, `DEID_DEFAULT_POLICY`, `DEID_SALT`, `MAX_TEXT_SIZE`.


## Endpoints

| Method | Path                  | Body                                        | Description                                   |
|-------:|-----------------------|---------------------------------------------|-----------------------------------------------|
|  POST  | `/api/v1/deid`        | `{ "text": str, "lang_hint"?: "en"\|"el" }` | De‑identify inline text                        |
|  POST  | `/api/v1/deid/file`   | multipart `files[]` (+`lang_hint` form)     | De‑identify uploaded text file(s)              |
|   GET  | `/api/v1/config`      | —                                           | Get current policy map + default policy        |
|   PUT  | `/api/v1/config`      | `{ "default_policy"?: str, "policy_map"?: {} }` | Update in‑memory policy/default (MVP)   |
|   GET  | `/api/v1/health`      | —                                           | Health check + app version                     |
|   GET  | `/api/v1/metrics/last`| —                                           | Last evaluation metrics (if any)               |

Response (POST `/deid`)

```json
{
  "original_len": 1234,
  "result_text": "...",
  "entities": [{"label": "EMAIL", "span": [0, 10], "action": "hash"}],
  "time_ms": 7
}
```


## Why It Matters

- Healthcare: remove PHI from notes/referrals for analytics, model training, and safe sharing.
- Legal/Compliance: enforce GDPR/HIPAA minimization by policy (mask/hash/redact) with audit logs.
- Multilingual: supports English and Greek (en/el) with regex + spaCy NER and Greek address heuristics.


## Architecture (MVP)

```
             ┌──────────┐         REST          ┌────────────┐
Browser/UI → │  FastAPI │  /api/v1 (JSON)  →    │  Engine    │
 (Jinja2)    │  app.main│ ────────────────      │ De‑ID +    │
  /static    └──────────┘                        │ Policies   │
       ▲           │                             └────────────┘
       │           │ Celery tasks (async)                │
       │           ▼                                     │
     HTML     ┌──────────┐        Broker/Backend  ┌───────────┐
  templates   │  Worker  │ <────────────────────→ │  Redis    │
              │ (Celery) │                         └───────────┘
              └──────────┘
                   │  SQLAlchemy ORM
                   ▼
              ┌───────────┐
              │ Postgres  │ (DeidLog, MetricRun)
              └───────────┘
```


## Security (MVP stance)

- API Key (optional): set `API_KEY` in `.env` and send `X-API-Key` header. If not set, key is not enforced (demo mode).
- CORS: allowlist includes localhost/Docker defaults; tighten in production.
- Rate limiting: use an API gateway or reverse proxy (e.g., NGINX/Traefik with limit_req); built‑in limiter planned.
- Data at rest: Postgres; ensure volumes/disks are encrypted in production.
 - Request size: bodies > 1MB are rejected with HTTP 413 by default (see middleware in `app/main.py`).


## Synthetic Data & Evaluation

```bash
# Generate mixed EL/EN dataset (JSONL)
python scripts/generate_synthetic.py --n 1000 --lang-mix 0.5

# Evaluate and (optionally) write metrics to DB
python scripts/evaluate.py --dataset scripts/dataset.jsonl \
  --out scripts/summary.json --write-db

# View last metrics via API
curl -s http://localhost:8000/api/v1/metrics/last | jq
```

- The evaluator reports per‑label precision/recall/F1 (micro/macro), docs/sec, and false‑negative rate.
- A JSON summary is written next to the dataset; DB results appear at `/api/v1/metrics/last`.


## Testing & Coverage

Docker (recommended)

```bash
# Build, migrate, and run tests with coverage
docker compose build api
docker compose up -d postgres redis api
docker compose exec -T api alembic upgrade head
docker compose exec -T api pip install coverage

docker compose exec -T -e PYTHONPATH=/app api coverage run -m pytest
docker compose exec -T -e PYTHONPATH=/app api coverage report -m
```

Local

```bash
pytest -q
coverage run -m pytest && coverage report -m && coverage html  # optional
```

CI

- GitHub Actions runs tests + coverage on every push/PR (see `.github/workflows/ci.yml`).


## Releases

Cut a tagged release to build and publish images to GHCR and create a GitHub Release with autogenerated notes.

```bash
git tag v0.2.0
git push origin v0.2.0
```

This triggers `.github/workflows/release.yml` to:
- Build and push Docker images:
  - `ghcr.io/<OWNER>/aegis-deid-api:v0.2.0` and `:latest`
  - `ghcr.io/<OWNER>/aegis-deid-worker:v0.2.0` and `:latest`
- Attach coverage.xml, README, CHANGELOG to the GitHub Release.


## Roadmap

- Presidio backend and custom recognizers for richer PII coverage.
- Persisted policy profiles per project + versioned policy history.
- Redacted‑PDF pipeline (doc → text → de‑id → PDF w/ overlays).
- AuthN/Z: API keys + OAuth2, roles/scopes, audit trails.
- Rate limiting and request quotas; per‑tenant isolation.
- Active learning: error analysis UI + annotation loops.


## License

MIT — see [LICENSE](./LICENSE).


## Contributing

PRs and issues are welcome! Please:

1) Open an issue describing the change.
2) Include tests. Run `pytest -q` and ensure coverage isn’t decreasing.
3) Follow the project style; keep diffs minimal and focused.


## Code of Conduct

This project follows the spirit of the Contributor Covenant. Be kind and respectful. Harassment or abuse will not be tolerated.


## Security Policy

If you find a vulnerability, please email the maintainers or open a private security advisory. Avoid filing public issues with sensitive details.

- Scope: API, worker tasks, scripts.
- Please include reproduction steps and environment details.
