"""Application settings loaded from environment."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from shadi_fhir.mcp_server import FHIRMCPServer


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    fhir_base_url: str = ""
    fhir_client_id: str = ""
    fhir_client_secret: str = ""
    fhir_token_url: str = ""
    notification_endpoint: str = Field(
        default="",
        validation_alias="NOTIFICATION_ENDPOINT",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    intake_queue: str = Field(default="shadi:intake", validation_alias="INTAKE_QUEUE")
    fhir_webhook_secret: str = Field(default="", validation_alias="FHIR_WEBHOOK_SECRET")

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
    return FHIRMCPServer(
        settings.fhir_base_url,
        settings.fhir_client_id,
        settings.fhir_client_secret,
        settings.fhir_token_url,
        notification_endpoint=settings.notification_endpoint,
        redis_url=settings.redis_url,
        intake_queue=settings.intake_queue,
    )
