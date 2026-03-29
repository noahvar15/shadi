"""A2A (agent-to-agent) message protocol for the debate round.

Agents communicate via structured messages rather than freeform text.
Each message has one of three intents:

  ENDORSE  — the sender agrees with the target's diagnosis candidate
  CHALLENGE — the sender disputes a candidate and must supply a counter-argument
  MODIFY   — the sender proposes a modification (confidence adjustment, evidence
              addition, or next-step change) to an existing candidate

The orchestrator collects all messages, computes consensus scores, and tracks
which diagnoses were challenged without rebuttal (divergence).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


def _utc_now() -> datetime:
    return datetime.now(UTC)


class MessageIntent(str, Enum):
    ENDORSE = "ENDORSE"
    CHALLENGE = "CHALLENGE"
    MODIFY = "MODIFY"


class ConfidenceDelta(BaseModel):
    """Proposed confidence adjustment carried in MODIFY messages."""

    previous: Annotated[float, Field(ge=0.0, le=1.0)]
    proposed: Annotated[float, Field(ge=0.0, le=1.0)]
    rationale: str


class A2AMessage(BaseModel):
    """Single agent-to-agent debate message.

    Decision: flat message schema (not nested conversation threads) so the
    orchestrator can process all round-N messages before starting round N+1
    without needing to reconstruct thread state.
    """

    message_id: UUID = Field(default_factory=uuid4)
    sent_at: datetime = Field(default_factory=_utc_now)

    # Routing
    sender: str          # agent name, e.g. "cardiology"
    recipient: str       # agent name or "orchestrator" for broadcast
    case_id: UUID

    # Content
    intent: MessageIntent
    target_diagnosis: str          # display name of the diagnosis being addressed
    target_diagnosis_snomed: str | None = None

    # Intent-specific payload
    argument: str                  # free-text clinical argument (required for all intents)
    evidence_codes: list[str] = Field(default_factory=list)   # PubMed IDs or guideline refs
    confidence_delta: ConfidenceDelta | None = None            # only for MODIFY

    # Round tracking — set by the orchestrator before broadcasting
    round_number: int = 1

    @model_validator(mode="after")
    def validate_intent_payload(self) -> "A2AMessage":
        if self.intent == MessageIntent.CHALLENGE and not self.argument:
            raise ValueError("CHALLENGE messages must include an argument")
        if self.intent == MessageIntent.MODIFY and self.confidence_delta is None:
            raise ValueError("MODIFY messages must include a confidence_delta")
        return self


class DebateRound(BaseModel):
    """All messages exchanged in a single debate round for one case."""

    round_number: int
    case_id: UUID
    messages: list[A2AMessage] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=_utc_now)
    closed_at: datetime | None = None

    @property
    def endorsements(self) -> list[A2AMessage]:
        return [m for m in self.messages if m.intent == MessageIntent.ENDORSE]

    @property
    def challenges(self) -> list[A2AMessage]:
        return [m for m in self.messages if m.intent == MessageIntent.CHALLENGE]

    @property
    def modifications(self) -> list[A2AMessage]:
        return [m for m in self.messages if m.intent == MessageIntent.MODIFY]

    def challenged_diagnoses(self) -> set[str]:
        return {m.target_diagnosis for m in self.challenges}

    def endorsed_diagnoses(self) -> set[str]:
        return {m.target_diagnosis for m in self.endorsements}
