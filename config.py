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

Specialists and evidence claim evaluation use Ollama Meditron (``MEDITRON_MODEL``;
default ``meditron:70b``). See ADR-004.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=[".env", ".env.demo"], extra="ignore")

    # ── Inference servers ──────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    # Optional; retained for tooling or future use — specialists use Ollama (ADR-004).
    VLLM_BASE_URL: str = "http://localhost:8080/v1"
    # Ollama library tag for Meditron (specialists ×4 + evidence claim eval).
    MEDITRON_MODEL: str = "meditron:70b"
    # Orchestrator synthesis + other Ollama chat models (must match ``ollama pull`` names).
    ORCHESTRATOR_MODEL: str = "deepseek-r1:32b"
    SAFETY_MODEL: str = "phi4:14b"
    EVIDENCE_EMBED_MODEL: str = "nomic-embed-text"

    # Live inference: long reads for 70B-class models; connect can be slow on cold start.
    LLM_HTTP_TIMEOUT_SECONDS: float = 600.0
    OLLAMA_EMBED_TIMEOUT_SECONDS: float = 180.0

    # Fan-out four specialists at once can overload a single-GPU Ollama queue; set false to run sequentially.
    SPECIALISTS_PARALLEL: bool = False

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
