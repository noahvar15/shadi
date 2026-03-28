"""FHIR R4 MCP server — subscribes to patient encounter events.

Normalizes incoming FHIR resources into CaseObjects and enqueues them
for the intake agent.
"""

from __future__ import annotations

import structlog

from fhir.normalizer import FHIRNormalizer

logger = structlog.get_logger()


class FHIRMCPServer:
    """Subscribes to FHIR R4 encounter events from Epic/Cerner.

    Decision: Using FHIR subscriptions (push) rather than polling.
    See ADR-001 for rationale and known unknowns around vendor support.
    """

    def __init__(self, base_url: str, client_id: str, client_secret: str, token_url: str) -> None:
        self._base_url = base_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._normalizer = FHIRNormalizer()

    async def start(self) -> None:
        """Authenticate and register encounter subscription."""
        # TODO: implement SMART on FHIR OAuth2 client credentials flow
        # TODO: register FHIR Subscription resource for Encounter events
        logger.info("fhir.mcp_server.started", base_url=self._base_url)

    async def stop(self) -> None:
        # TODO: deregister subscription on clean shutdown
        logger.info("fhir.mcp_server.stopped")
