# Deployment

The root `Dockerfile` builds the React frontend and serves it with FastAPI from one container.

## Build and Run

```bash
docker build -t codecoach .
docker run --rm \
  -p 8000:8000 \
  -v codecoach-data:/app/data \
  codecoach
```

Check `http://localhost:8000/health`, then open `http://localhost:8000`.

## Production Variables

```text
CODECOACH_ENV=production
CODECOACH_CORS_ORIGINS=https://<your-domain>
CODECOACH_ALLOWED_HOSTS=<your-domain>
CODECOACH_ENABLE_DOCS=false
CODECOACH_EXPOSE_TRACES=false
CODECOACH_AUTH_REQUIRED=true
CODECOACH_USE_LLM=false
```

When enabling an OpenAI-compatible provider, configure secrets only in the deployment platform:

```text
CODECOACH_USE_LLM=true
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=<secret>
LLM_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=60
LLM_FAILURE_COOLDOWN_SECONDS=10
CODECOACH_LLM_TRACE_AGENTS=false
```

## Public-Service Checklist

- Mount persistent storage at `/app/data` and test restore procedures.
- Terminate TLS at the platform or reverse proxy.
- Restrict CORS and allowed hosts to the production domain.
- Keep API documentation and Agent traces disabled.
- Add request limits, account limits, LLM quotas, monitoring, and alerts.
- Rotate any secret that has appeared in logs, terminals, screenshots, or support conversations.
- Review the authentication and privacy model before accepting real student data.

The image runs as a non-root user. It can be deployed on any Docker-compatible platform, including Zeabur, Fly.io, Railway, Render, or a self-hosted container service.
