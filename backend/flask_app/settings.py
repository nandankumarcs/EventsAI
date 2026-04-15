from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _get_list(name: str, default: str) -> list[str]:
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _normalize_database_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        return "postgresql+psycopg://" + raw.removeprefix("postgres://")
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw.removeprefix("postgresql://")
    return raw


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    frontend_dir: Path
    frontend_assets_dir: Path

    debug: bool
    secret_key: str

    allowed_hosts: list[str]
    cors_allowed_origins: list[str]

    database_url: str | None

    use_ollama: bool
    agent_slow_log_seconds: float
    ollama_host: str
    ollama_model: str
    ollama_llm_timeout_seconds: float

    openai_api_key: str | None
    openai_chat_model: str
    openai_resolver_model: str
    openai_llm_timeout_seconds: float

    port: int

    @classmethod
    def from_env(cls) -> "Settings":
        base_dir = Path(__file__).resolve().parent.parent
        frontend_dir = base_dir / "public"
        frontend_assets_dir = frontend_dir / "assets"

        database_url = os.getenv("DATABASE_URL")
        normalized_db_url = _normalize_database_url(database_url) if database_url else None

        return cls(
            base_dir=base_dir,
            frontend_dir=frontend_dir,
            frontend_assets_dir=frontend_assets_dir,
            debug=_get_bool("DJANGO_DEBUG", True),
            secret_key=os.getenv("DJANGO_SECRET_KEY", "dev-attend-secret-key"),
            allowed_hosts=_get_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost"),
            cors_allowed_origins=_get_list(
                "DJANGO_CORS_ALLOWED_ORIGINS",
                "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174",
            ),
            database_url=normalized_db_url,
            use_ollama=_get_bool("USE_OLLAMA", False),
            agent_slow_log_seconds=float(os.getenv("AGENT_SLOW_LOG_SECONDS", "2.5")),
            ollama_host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "gemma4:e2b"),
            ollama_llm_timeout_seconds=float(os.getenv("OLLAMA_LLM_TIMEOUT_SECONDS", "20.0")),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
            openai_resolver_model=os.getenv("OPENAI_RESOLVER_MODEL", "gpt-4.1-mini"),
            openai_llm_timeout_seconds=float(os.getenv("OPENAI_LLM_TIMEOUT_SECONDS", "20.0")),
            port=int(os.getenv("PORT", "8000")),
        )
