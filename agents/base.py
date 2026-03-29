"""Base agent interface for all Shadi agents.

Every agent in the pipeline — intake, specialist, evidence, safety, and
orchestrator — extends BaseAgent. The contract is intentionally minimal:
receive a CaseObject, produce a typed result, emit structured logs.

Inference routing
-----------------
Two inference servers run in parallel (see ADR-002):

- **vLLM** (``VLLM_BASE_URL``, default port 8080) — serves ``meditron:70b``
  with hot-swappable LoRA adapters for the four specialist agents. Required
  because Ollama does not support LoRA hot-swapping.

- **Ollama** (``OLLAMA_BASE_URL``, default port 11434) — serves all other
  models: ``alibayram/medgemma:27b`` (image), ``qwen2.5:7b`` (intake),
  ``nomic-embed-text`` (evidence retrieval), ``phi4:14b`` (safety veto),
  ``deepseek-r1:32b`` (orchestrator).

Both expose an OpenAI-compatible ``/v1`` endpoint. Subclasses select the
correct server by setting ``inference_url`` and ``model`` as class attributes.
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

    Class attributes
    ----------------
    name : str
        Human-readable name used in logs and A2A messages.
    domain : str
        Domain label used for LoRA adapter selection and message routing.
    inference_url : str
        Base URL of the inference server this agent calls. Set to
        ``VLLM_BASE_URL`` for specialist agents (LoRA hot-swap) or
        ``OLLAMA_BASE_URL`` for all other agents.
    model : str
        Model or adapter name passed to the inference endpoint.

        Specialist agents use the LoRA adapter name (e.g. ``"cardiology"``);
        all others use the Ollama model tag (e.g. ``"phi4:14b"``).
    """

    #: Human-readable name used in logs and A2A messages.
    name: str

    #: Domain label used for LoRA adapter selection and message routing.
    domain: str

    #: OpenAI-compatible inference endpoint (vLLM or Ollama). See module docstring.
    inference_url: str

    #: Model name or LoRA adapter name passed to the inference endpoint.
    model: str

    def __init__(self) -> None:
        self._log = logger.bind(agent=self.name, domain=self.domain, model=self.model)

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
            self.post_reason(case, result)
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
        1. Build a domain-specific prompt from ``case``
        2. POST to ``self.inference_url`` using ``self.model`` as the model name
           (OpenAI-compatible chat completions endpoint)
        3. Parse the response into a typed result object
        4. Return the result — do NOT write to any shared state here

        Specialist agents call vLLM with a LoRA adapter name; all other agents
        call Ollama with a model tag. The calling convention is identical for
        both because both servers implement the OpenAI ``/v1/chat/completions``
        spec. See ADR-002.

        Side effects belong in the orchestrator, not in ``reason``.

        If an agent must update the ``CaseObject`` after structured output is
        known (e.g. intake codes), implement :meth:`post_reason` instead of
        mutating ``case`` inside ``reason``.
        """
        ...

    def post_reason(self, case: CaseObject, result: TResult) -> None:
        """Run after ``reason`` returns; default no-op.

        Use for side effects that should not live inside ``reason`` — for
        example merging intake-extracted codes onto ``case`` while keeping
        ``reason`` free of shared-state writes.
        """
        return None

    def describe(self) -> dict[str, Any]:
        """Return a summary of this agent for logging and A2A messages."""
        return {"name": self.name, "domain": self.domain, "model": self.model}
