"""Debate round orchestration — collects A2A messages, tracks consensus."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from a2a.protocol import A2AMessage, DebateRound, MessageIntent


class DebateManager:
    """Manages one or more debate rounds for a case.

    The orchestrator calls `open_round`, broadcasts specialist findings,
    collects `A2AMessage` replies via `add_message`, then calls
    `close_round` to get a summary used for synthesis.
    """

    def __init__(self, case_id: UUID) -> None:
        self.case_id = case_id
        self._rounds: list[DebateRound] = []
        self._current: DebateRound | None = None

    def open_round(self) -> DebateRound:
        round_number = len(self._rounds) + 1
        self._current = DebateRound(round_number=round_number, case_id=self.case_id)
        return self._current

    def add_message(self, message: A2AMessage) -> None:
        if self._current is None:
            raise RuntimeError("No open debate round")
        message.round_number = self._current.round_number
        self._current.messages.append(message)

    def close_round(self) -> DebateRound:
        if self._current is None:
            raise RuntimeError("No open debate round")
        from datetime import datetime
        self._current.closed_at = datetime.utcnow()
        self._rounds.append(self._current)
        closed = self._current
        self._current = None
        return closed

    def consensus_scores(self) -> dict[str, float]:
        """Return a consensus score [0,1] per diagnosis across all closed rounds.

        Score = endorsements / (endorsements + challenges). Uncontested
        diagnoses score 1.0; diagnoses with only challenges score 0.0.
        """
        endorse_counts: dict[str, int] = defaultdict(int)
        challenge_counts: dict[str, int] = defaultdict(int)

        for round_ in self._rounds:
            for msg in round_.messages:
                if msg.intent == MessageIntent.ENDORSE:
                    endorse_counts[msg.target_diagnosis] += 1
                elif msg.intent == MessageIntent.CHALLENGE:
                    challenge_counts[msg.target_diagnosis] += 1

        all_diagnoses = set(endorse_counts) | set(challenge_counts)
        scores: dict[str, float] = {}
        for dx in all_diagnoses:
            e = endorse_counts[dx]
            c = challenge_counts[dx]
            scores[dx] = e / (e + c) if (e + c) > 0 else 1.0
        return scores

    def divergent_diagnoses(self, threshold: float = 0.5) -> list[str]:
        """Return diagnoses where consensus score is below `threshold`."""
        return [dx for dx, score in self.consensus_scores().items() if score < threshold]
