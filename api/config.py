"""Application settings (shared with agents via env — see cross-track-dependencies)."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
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
        # Try .env first (git-ignored personal override), then fall back to the
        # committed .env.demo so teammates can run the stack without any manual cp.
        env_file=[".env", ".env.demo"],
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
    intake_queue: str = Field(default="arq:intake", validation_alias="INTAKE_QUEUE")
    api_secret_key: str = Field(..., validation_alias="API_SECRET_KEY")
    # DEP-1 (cross-track-dependencies): use until Noah #28 contract is merged in your fork
    stub_case_intake: bool = Field(default=False, validation_alias="SHADI_STUB_CASE_INTAKE")
    stub_patient_search: bool = Field(default=False, validation_alias="SHADI_STUB_PATIENT_SEARCH")

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
    fhir_webhook_secret: str = Field(default="", validation_alias="FHIR_WEBHOOK_SECRET")

    @field_validator("fhir_webhook_secret", mode="after")
    @classmethod
    def fhir_webhook_secret_not_placeholder(cls, v: str) -> str:
        t = v.strip().lower()
        if t and t in _PLACEHOLDER_API_SECRETS:
            msg = "FHIR_WEBHOOK_SECRET must not be a placeholder or weak default (same rules as API_SECRET_KEY)."
            raise ValueError(msg)
        return v

    @property
    def fhir_mcp_enabled(self) -> bool:
        return bool(
            self.fhir_base_url.strip()
            and self.fhir_client_id.strip()
            and self.fhir_client_secret.strip()
            and self.fhir_token_url.strip()
            and self.notification_endpoint.strip()
            and self.fhir_webhook_secret.strip()
        )


def build_fhir_mcp_server(settings: Settings) -> FHIRMCPServer:
    from shadi_fhir.mcp_server import FHIRMCPServer

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
