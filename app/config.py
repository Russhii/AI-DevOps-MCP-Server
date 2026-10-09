"""Settings come from environment variables (loaded from .env). Nothing is hardcoded."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # does not override variables that are already set


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    github_token: str | None
    api_keys: str          # "name:key:read+write,name2:key2:read"
    require_auth: bool
    host: str
    port: int
    log_level: str
    groq_api_key: str | None
    groq_model: str
    mcp_url: str           # used by client.py / agent.py
    mcp_api_key: str | None


def get_settings() -> Settings:
    """Read settings fresh each time so tests can change the environment."""
    port = int(os.getenv("PORT", "8000"))
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./tasks.db"),
        github_token=os.getenv("GITHUB_TOKEN") or None,
        api_keys=os.getenv("API_KEYS", ""),
        require_auth=_bool("REQUIRE_AUTH", True),
        host=os.getenv("HOST", "127.0.0.1"),
        port=port,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        mcp_url=os.getenv("MCP_URL", f"http://127.0.0.1:{port}/mcp"),
        mcp_api_key=os.getenv("MCP_API_KEY") or None,
    )
