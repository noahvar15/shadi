"""Application settings (shared with agents via env — see cross-track-dependencies)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(validation_alias="DATABASE_URL")
    redis_url: str = Field(validation_alias="REDIS_URL")
    vllm_base_url: str = Field(default="http://localhost:8080/v1", validation_alias="VLLM_BASE_URL")
    ollama_base_url: str = Field(
        default="http://localhost:11434/v1",
        validation_alias="OLLAMA_BASE_URL",
    )
    intake_queue: str = Field(default="arq:intake", validation_alias="INTAKE_QUEUE")
    api_secret_key: str = Field(validation_alias="API_SECRET_KEY")
    # DEP-1 (cross-track-dependencies): use until Noah #28 contract is merged in your fork
    stub_case_intake: bool = Field(default=False, validation_alias="SHADI_STUB_CASE_INTAKE")


@lru_cache
def get_settings() -> Settings:
    return Settings()
