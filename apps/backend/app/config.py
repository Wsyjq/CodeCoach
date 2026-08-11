import os

from dotenv import load_dotenv
from pydantic import BaseModel


load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: list[str] | None = None) -> list[str]:
    value = os.getenv(name)
    if value is None:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseModel):
    app_name: str = "CodeCoach API"
    app_env: str = os.getenv("CODECOACH_ENV", "development")
    demo_user_id: str = "demo_user"
    cors_origins: list[str] = _env_list(
        "CODECOACH_CORS_ORIGINS",
        ["http://localhost:5173", "http://127.0.0.1:5173"],
    )
    cors_allow_credentials: bool = _env_bool("CODECOACH_CORS_ALLOW_CREDENTIALS", True)
    allowed_hosts: list[str] = _env_list("CODECOACH_ALLOWED_HOSTS")
    static_dir: str = os.getenv("CODECOACH_STATIC_DIR", "")
    basic_auth_username: str = os.getenv("CODECOACH_BASIC_AUTH_USERNAME", "")
    basic_auth_password: str = os.getenv("CODECOACH_BASIC_AUTH_PASSWORD", "")
    enable_hsts: bool = _env_bool(
        "CODECOACH_ENABLE_HSTS",
        os.getenv("CODECOACH_ENV", "development") == "production",
    )
    enable_docs: bool = _env_bool(
        "CODECOACH_ENABLE_DOCS",
        os.getenv("CODECOACH_ENV", "development") != "production",
    )
    expose_traces: bool = _env_bool(
        "CODECOACH_EXPOSE_TRACES",
        os.getenv("CODECOACH_ENV", "development") != "production",
    )
    auth_required: bool = _env_bool("CODECOACH_AUTH_REQUIRED", True)
    maintenance_mode: bool = _env_bool("CODECOACH_MAINTENANCE_MODE", False)
    maintenance_message: str = os.getenv("CODECOACH_MAINTENANCE_MESSAGE", "")
    use_llm: bool = _env_bool("CODECOACH_USE_LLM", False)
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    llm_failure_cooldown_seconds: float = float(os.getenv("LLM_FAILURE_COOLDOWN_SECONDS", "0"))
    llm_trace_agents: bool = _env_bool("CODECOACH_LLM_TRACE_AGENTS", False)

    @property
    def basic_auth_enabled(self) -> bool:
        return bool(self.basic_auth_username or self.basic_auth_password)


settings = Settings()
