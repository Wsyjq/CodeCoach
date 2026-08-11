# CodeCoach

[![CI](https://github.com/Wsyjq/CodeCoach/actions/workflows/ci.yml/badge.svg)](https://github.com/Wsyjq/CodeCoach/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Wsyjq/CodeCoach/actions/workflows/codeql.yml/badge.svg)](https://github.com/Wsyjq/CodeCoach/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

CodeCoach 是一个面向 C 语言初学者的开源学习助手。它把知识问答、题目理解、分层提示、代码纠错、错题复盘和学习记忆放在同一个工作台中，并展示每次请求经过的 Agent 与工具。

> 项目状态：Beta / 教学 Demo。默认使用本地确定性逻辑，不配置大模型也能运行。当前版本不应直接作为无人值守的公共生产服务。

## Features

- 六类学习服务：知识问答、题意拆解、分层提示、代码纠错、学习问数和错题复盘。
- C 语言轻量规则分析：覆盖 `scanf` 地址、赋值与比较、数组边界、未初始化变量等常见问题。
- 学习闭环：SQLite 保存会话、错题记忆、复习状态和学习统计。
- 检索增强：默认使用 MIT 教学知识卡片进行本地检索，并保留可选向量库适配器。
- 可选大模型：支持 OpenAI-compatible `POST /chat/completions` 接口，失败时自动回退。
- 可观察流程：前端展示 Agent Trace、相似错误提醒和复盘卡片。
- 单镜像部署：Vite 构建前端，FastAPI 同源提供 API 和静态页面。

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite |
| Backend | Python 3.10+, FastAPI, Pydantic |
| Persistence | SQLite |
| Vector search | Local JSONL; optional ChromaDB adapter |
| Optional LLM | OpenAI-compatible HTTP API |
| Tests | pytest, frontend TypeScript build, E2E smoke scripts |

## Project Structure

```text
CodeCoach/
  apps/
    backend/              FastAPI API, Agent orchestration, tools and tests
    frontend/             React learning workspace
  data/
    knowledge_seed/       reviewed first-party MIT knowledge cards
    runtime/              local database and vector store, ignored by Git
  docs/                   architecture, API contract and deployment guide
  scripts/                local development and verification scripts
  tests/e2e/              end-to-end smoke tests
```

## Quick Start

Requirements:

- Python 3.10 or newer
- Node.js 22 or newer
- npm 10 or newer

Start the backend:

```bash
cd apps/backend
python -m venv .venv
```

Activate the environment on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Or on macOS/Linux:

```bash
source .venv/bin/activate
```

Install and run:

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Start the frontend in another terminal:

```bash
cd apps/frontend
npm ci
npm run dev
```

Open `http://localhost:5173`, register a local account, and start a learning session.

## Optional LLM

The application works without an LLM. To enable an OpenAI-compatible provider:

```bash
cd apps/backend
cp .env.example .env
```

Windows PowerShell equivalent:

```powershell
Copy-Item .env.example .env
```

Set these values only in the local `.env` file or your deployment platform:

```text
CODECOACH_USE_LLM=true
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=<your-secret-key>
LLM_MODEL=gpt-4o-mini
```

Never put a real key in Git, frontend variables, logs, screenshots, issues, or test fixtures.

## Docker

```bash
docker build -t codecoach .
docker run --rm -p 8000:8000 -v codecoach-data:/app/data codecoach
```

Open `http://localhost:8000`. See [Deployment](./docs/deployment.md) before exposing the service publicly.

## Verification

Backend:

```bash
cd apps/backend
pip install -r requirements-dev.txt
python -m compileall app
python -m pytest tests
```

Frontend:

```bash
cd apps/frontend
npm ci
npm run build
```

Windows users can run `scripts/check_backend.ps1` and `scripts/check_frontend.ps1` from the repository root.

Browser regression against a running service on `http://127.0.0.1:18101`:

```bash
pip install -r tests/e2e/requirements.txt
python -m playwright install chromium
python tests/e2e/e2e_auth_regression.py
```

## Knowledge Data

Committed cards under `data/knowledge_seed/` are maintained as first-party MIT content. Every card records `source` and an SPDX `license` value. Generated databases, vector stores, user records, and imported third-party corpora are never committed.

Knowledge contributions must include verifiable provenance. Do not submit copied tutorials, books, courseware, solution repositories, or generated derivatives whose redistribution rights are unclear. See [Data](./data/README.md) and [Contributing](./CONTRIBUTING.md).

## Documentation

- [Architecture](./docs/architecture.md)
- [API Contract](./docs/api_contract.md)
- [Deployment](./docs/deployment.md)
- [Security Policy](./SECURITY.md)

## Security and Limitations

- LLM calls are disabled by default.
- ChromaDB is not installed by default while its current release has an unresolved security advisory; local JSONL retrieval remains available.
- Public deployments need rate limiting, abuse controls, HTTPS, backups, monitoring, and a reviewed authentication policy.
- `/api/traces` can contain user prompts and tool inputs; keep it disabled on public deployments.
- This project is an educational assistant, not a secure C sandbox or an authoritative grading system.

## Contributing

Issues and pull requests are welcome. Read [CONTRIBUTING.md](./CONTRIBUTING.md) and the [Code of Conduct](./CODE_OF_CONDUCT.md) before contributing.

## License

Code, documentation, and first-party knowledge cards are released under the [MIT License](./LICENSE). Third-party packages keep their own licenses; see [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md).
