# Backend Tests

Backend smoke tests, API contract tests, tool tests, SQLite memory tests, and LLM fallback tests live here.

Run from `apps/backend`:

```bash
python -m pytest tests
```

Or from the project root:

```powershell
.\scripts\check_backend.ps1
```

Current coverage:

- `/health` returns `ok`.
- `/api/chat` returns stable responses for debug, knowledge QA, data QA, hint, review, and problem-understanding scenarios.
- `/api/memories`, `/api/stats/summary`, `/api/reviews/due`, and `/api/knowledge/sources` keep frontend-compatible response shapes.
- `analyze_c_code_light` detects common C mistakes.
- JSONL knowledge cards load from `data/knowledge_seed`, power `search_knowledge_base`, and fall back to demo cards when files are missing.
- SQLite seed data, review-card writes, stats, and similarity recall work against an isolated test database.
- LLM disabled / missing-key fallback keeps the demo deterministic.
- Real LLM calls are optional and skipped by default. To run the OpenAI-compatible integration smoke test, configure `.env` and set `CODECOACH_RUN_LLM_TESTS=true`.

Run the optional real LLM smoke test:

```powershell
$env:CODECOACH_RUN_LLM_TESTS="true"
python -m pytest tests/test_llm_integration.py
Remove-Item Env:\CODECOACH_RUN_LLM_TESTS
```
