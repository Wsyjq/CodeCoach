import base64
import binascii
import secrets
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, chat, knowledge, memories, stats, traces
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)

if settings.allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials and "*" not in settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.enable_hsts:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.middleware("http")
async def enforce_maintenance_mode(request: Request, call_next):
    if not settings.maintenance_mode:
        return await call_next(request)
    if request.url.path in {"/health", "/api/status"} or not request.url.path.startswith("/api/"):
        return await call_next(request)
    return JSONResponse(
        {"detail": settings.maintenance_message},
        status_code=503,
        headers={"Retry-After": "3600"},
    )


@app.middleware("http")
async def require_basic_auth(request: Request, call_next):
    if not settings.basic_auth_enabled or request.url.path == "/health":
        return await call_next(request)

    if not settings.basic_auth_username or not settings.basic_auth_password:
        return Response("Basic auth is partially configured", status_code=500)

    if _has_valid_basic_auth(request.headers.get("Authorization", "")):
        return await call_next(request)

    return Response(
        "Authentication required",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="CodeCoach"'},
    )


def _has_valid_basic_auth(authorization: str) -> bool:
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "basic" or not credentials:
        return False
    try:
        decoded = base64.b64decode(credentials, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    username, separator, password = decoded.partition(":")
    if not separator:
        return False
    return secrets.compare_digest(username, settings.basic_auth_username) and secrets.compare_digest(
        password,
        settings.basic_auth_password,
    )

app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(memories.router, prefix="/api", tags=["memories"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(knowledge.router, prefix="/api", tags=["knowledge"])
app.include_router(traces.router, prefix="/api", tags=["traces"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
def status() -> dict[str, str | bool]:
    return {
        "status": "maintenance" if settings.maintenance_mode else "ok",
        "maintenance": settings.maintenance_mode,
        "message": settings.maintenance_message if settings.maintenance_mode else "",
    }


static_dir = Path(settings.static_dir) if settings.static_dir else None
if static_dir and static_dir.is_dir():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
