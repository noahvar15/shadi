"""Application-wide settings loaded from environment variables / .env file.

Usage
-----
    from config import settings

    url = settings.OLLAMA_BASE_URL

Mock mode
---------
Set ``MOCK_LLM=true`` (the default) to bypass real inference calls during
local development. Flip to ``false`` when running on the DGX with models
downloaded. See ``agents/_llm.py`` for the implementation.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Inference servers ──────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    VLLM_BASE_URL: str = "http://localhost:8080/v1"

    # ── Database ───────────────────────────────────────────────────────────
    # SQLAlchemy-style DSN (used by SQLAlchemy ORM and the API layer).
    # EvidenceAgent strips the "+asyncpg" dialect prefix when opening a raw
    # asyncpg connection for the pgvector similarity query.
    DATABASE_URL: str = "postgresql+asyncpg://shadi:shadi@localhost:5432/shadi"

    # ── Local-dev mock flag ────────────────────────────────────────────────
    # Default True so the agents run without downloaded models.
    # Set MOCK_LLM=false in .env (or the environment) on the DGX.
    MOCK_LLM: bool = True


settings = Settings()
