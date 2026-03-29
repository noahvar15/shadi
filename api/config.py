"""Application settings (shared with agents via env — see cross-track-dependencies)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from shadi_fhir.mcp_server import FHIRMCPServer

_PLACEHOLDER_API_SECRETS = frozenset(
    {
        "",
        "change-me",
        "changeme",
        "replace_me",
        "replace-me",
        "replace me",
        "secret",
        "password",
        "change-me-before-production",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(validation_alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    vllm_base_url: str = Field(default="http://localhost:8080/v1", validation_alias="VLLM_BASE_URL")
    ollama_base_url: str = Field(
        default="http://localhost:11434/v1",
        validation_alias="OLLAMA_BASE_URL",
    )
    meditron_model: str = Field(default="meditron:70b", validation_alias="MEDITRON_MODEL")
    intake_queue: str = Field(default="arq:intake", validation_alias="INTAKE_QUEUE")
    api_secret_key: str = Field(..., validation_alias="API_SECRET_KEY")
    # DEP-1 (cross-track-dependencies): use until Noah #28 contract is merged in your fork
    stub_case_intake: bool = Field(default=False, validation_alias="SHADI_STUB_CASE_INTAKE")

    @field_validator("api_secret_key", mode="after")
    @classmethod
    def api_secret_not_placeholder(cls, v: str) -> str:
        t = v.strip().lower()
        if t in _PLACEHOLDER_API_SECRETS:
            msg = "API_SECRET_KEY must be set to a non-placeholder value (not change-me, REPLACE_ME, etc.)"
            raise ValueError(msg)
        return v

    fhir_base_url: str = ""
    fhir_client_id: str = ""
    fhir_client_secret: str = ""
    fhir_token_url: str = ""
    notification_endpoint: str = Field(
        default="",
        validation_alias="NOTIFICATION_ENDPOINT",
    )

    @property
    def fhir_mcp_enabled(self) -> bool:
        return bool(
            self.fhir_base_url.strip()
            and self.fhir_client_id.strip()
            and self.fhir_client_secret.strip()
            and self.fhir_token_url.strip()
            and self.notification_endpoint.strip()
        )


def build_fhir_mcp_server(settings: Settings) -> FHIRMCPServer:
    return FHIRMCPServer(
        settings.fhir_base_url,
        settings.fhir_client_id,
        settings.fhir_client_secret,
        settings.fhir_token_url,
        notification_endpoint=settings.notification_endpoint,
        redis_url=settings.redis_url,
        intake_queue=settings.intake_queue,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
