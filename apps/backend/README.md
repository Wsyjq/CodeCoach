# CodeCoach Backend

FastAPI backend for CodeCoach. It provides authentication, chat orchestration, learning memories, review scheduling, statistics, knowledge retrieval, and optional OpenAI-compatible LLM calls.

## Run

```bash
python -m venv .venv
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

The API defaults to local deterministic behavior. Copy `.env.example` to `.env` only when configuration overrides are needed. ChromaDB is optional and is not installed by default while its current release has an unresolved security advisory.

## Main Endpoints

```text
GET  /health
POST /api/auth/register
POST /api/auth/login
POST /api/chat
GET  /api/stats/summary
GET  /api/memories
GET  /api/reviews/due
GET  /api/knowledge/sources
```

See `docs/api_contract.md` for request and response examples.

## Test

```bash
python -m compileall app
python -m pytest tests
```
