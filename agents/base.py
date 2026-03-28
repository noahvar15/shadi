"""Base agent interface for all Shadi agents.

Every agent in the pipeline — intake, specialist, evidence, safety, and
orchestrator — extends BaseAgent. The contract is intentionally minimal:
receive a CaseObject, produce a typed result, emit structured logs.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

import structlog

from agents.schemas import AgentResult, CaseObject

logger = structlog.get_logger()

TResult = TypeVar("TResult", bound=AgentResult)


class BaseAgent(ABC, Generic[TResult]):
    """Abstract base class for all Shadi agents.

    Subclasses must implement `reason`. The `run` method wraps `reason` with
    timing, structured logging, and error normalization — subclasses should
    not override `run`.
    """

    #: Human-readable name used in logs and A2A messages.
    name: str

    #: Domain label used for LoRA adapter selection and message routing.
    domain: str

    def __init__(self) -> None:
        self._log = logger.bind(agent=self.name, domain=self.domain)

    async def run(self, case: CaseObject) -> TResult:
        """Execute the agent and return a typed result.

        Wraps `reason` with timing and structured logging. Exceptions
        propagate to the orchestrator, which decides whether to retry or
        mark the agent as failed for this case.
        """
        start = time.monotonic()
        self._log.info("agent.start", case_id=case.case_id)
        try:
            result = await self.reason(case)
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log.info(
                "agent.complete",
                case_id=case.case_id,
                elapsed_ms=round(elapsed_ms, 1),
            )
            return result
        except Exception:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log.exception(
                "agent.error",
                case_id=case.case_id,
                elapsed_ms=round(elapsed_ms, 1),
            )
            raise

    @abstractmethod
    async def reason(self, case: CaseObject) -> TResult:
        """Domain-specific reasoning over the case.

        Implementations should:
        1. Build a domain-specific prompt from `case`
        2. Call the vLLM inference endpoint with the correct LoRA adapter
        3. Parse the response into a typed result object
        4. Return the result — do NOT write to any shared state here

        Side effects belong in the orchestrator, not in `reason`.
        """
        ...

    def describe(self) -> dict[str, Any]:
        """Return a summary of this agent for logging and A2A messages."""
        return {"name": self.name, "domain": self.domain}
