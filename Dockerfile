FROM node:22-alpine AS frontend

WORKDIR /app/apps/frontend
COPY apps/frontend/package*.json ./
RUN npm ci
COPY apps/frontend/ ./
RUN npm run build

FROM python:3.10-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/backend \
    PORT=8000 \
    CODECOACH_ENV=production \
    CODECOACH_STATIC_DIR=/app/static \
    CODECOACH_DATABASE_PATH=/app/data/codecoach.db \
    CODECOACH_VECTORSTORE_DIR=/app/data/vectorstore

WORKDIR /app

RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY apps/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/backend/app ./apps/backend/app
COPY data/knowledge_seed ./data/knowledge_seed
COPY LICENSE README.md THIRD_PARTY_NOTICES.md ./
COPY --from=frontend /app/apps/frontend/dist ./static

RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\", \"8000\")}/health', timeout=3)" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
