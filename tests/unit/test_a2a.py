"""Unit tests for the A2A debate protocol."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from a2a.debate import DebateManager
from a2a.protocol import A2AMessage, ConfidenceDelta, MessageIntent


CASE_ID = uuid4()


def _msg(intent: MessageIntent, diagnosis: str, *, sender: str = "cardiology", argument: str = "test arg", confidence_delta: ConfidenceDelta | None = None) -> A2AMessage:
    return A2AMessage(
        sender=sender,
        recipient="orchestrator",
        case_id=CASE_ID,
        intent=intent,
        target_diagnosis=diagnosis,
        argument=argument,
        confidence_delta=confidence_delta,
    )


class TestDebateManagerLifecycle:
    def test_open_and_close_round(self):
        dm = DebateManager(case_id=CASE_ID)
        rnd = dm.open_round()
        assert rnd.round_number == 1
        assert rnd.closed_at is None
        closed = dm.close_round()
        assert closed.closed_at is not None

    def test_add_message_without_open_round_raises(self):
        dm = DebateManager(case_id=CASE_ID)
        with pytest.raises(RuntimeError):
            dm.add_message(_msg(MessageIntent.ENDORSE, "AMI"))

    def test_close_without_open_raises(self):
        dm = DebateManager(case_id=CASE_ID)
        with pytest.raises(RuntimeError):
            dm.close_round()

    def test_sequential_rounds_increment(self):
        dm = DebateManager(case_id=CASE_ID)
        dm.open_round()
        dm.close_round()
        r2 = dm.open_round()
        assert r2.round_number == 2

    def test_message_round_number_set(self):
        dm = DebateManager(case_id=CASE_ID)
        dm.open_round()
        msg = _msg(MessageIntent.ENDORSE, "AMI")
        dm.add_message(msg)
        assert msg.round_number == 1


class TestConsensusScores:
    def test_all_endorsements(self):
        dm = DebateManager(case_id=CASE_ID)
        dm.open_round()
        dm.add_message(_msg(MessageIntent.ENDORSE, "AMI", sender="cardiology"))
        dm.add_message(_msg(MessageIntent.ENDORSE, "AMI", sender="neurology"))
        dm.close_round()
        scores = dm.consensus_scores()
        assert scores["AMI"] == 1.0

    def test_all_challenges(self):
        dm = DebateManager(case_id=CASE_ID)
        dm.open_round()
        dm.add_message(_msg(MessageIntent.CHALLENGE, "PE", sender="cardiology"))
        dm.add_message(_msg(MessageIntent.CHALLENGE, "PE", sender="pulmonology"))
        dm.close_round()
        scores = dm.consensus_scores()
        assert scores["PE"] == 0.0

    def test_mixed_endorsements_and_challenges(self):
        dm = DebateManager(case_id=CASE_ID)
        dm.open_round()
        dm.add_message(_msg(MessageIntent.ENDORSE, "Stroke", sender="neurology"))
        dm.add_message(_msg(MessageIntent.CHALLENGE, "Stroke", sender="cardiology"))
        dm.add_message(_msg(MessageIntent.ENDORSE, "Stroke", sender="pulmonology"))
        dm.close_round()
        scores = dm.consensus_scores()
        assert scores["Stroke"] == pytest.approx(2.0 / 3.0)

    def test_empty_round(self):
        dm = DebateManager(case_id=CASE_ID)
        dm.open_round()
        dm.close_round()
        assert dm.consensus_scores() == {}


class TestDivergentDiagnoses:
    def test_below_threshold_returned(self):
        dm = DebateManager(case_id=CASE_ID)
        dm.open_round()
        dm.add_message(_msg(MessageIntent.CHALLENGE, "PE", sender="cardiology"))
        dm.add_message(_msg(MessageIntent.CHALLENGE, "PE", sender="neurology"))
        dm.add_message(_msg(MessageIntent.ENDORSE, "AMI", sender="cardiology"))
        dm.close_round()
        divergent = dm.divergent_diagnoses(threshold=0.5)
        assert "PE" in divergent
        assert "AMI" not in divergent

    def test_all_above_threshold(self):
        dm = DebateManager(case_id=CASE_ID)
        dm.open_round()
        dm.add_message(_msg(MessageIntent.ENDORSE, "AMI"))
        dm.close_round()
        assert dm.divergent_diagnoses() == []


class TestA2AMessageValidation:
    def test_challenge_requires_argument(self):
        with pytest.raises(ValidationError):
            A2AMessage(
                sender="cardiology",
                recipient="orchestrator",
                case_id=CASE_ID,
                intent=MessageIntent.CHALLENGE,
                target_diagnosis="AMI",
                argument="",
            )

    def test_modify_requires_confidence_delta(self):
        with pytest.raises(ValidationError):
            A2AMessage(
                sender="cardiology",
                recipient="orchestrator",
                case_id=CASE_ID,
                intent=MessageIntent.MODIFY,
                target_diagnosis="AMI",
                argument="adjusting confidence",
                confidence_delta=None,
            )

    def test_modify_with_delta_succeeds(self):
        msg = A2AMessage(
            sender="cardiology",
            recipient="orchestrator",
            case_id=CASE_ID,
            intent=MessageIntent.MODIFY,
            target_diagnosis="AMI",
            argument="recalibrated",
            confidence_delta=ConfidenceDelta(previous=0.8, proposed=0.6, rationale="evidence weaker"),
        )
        assert msg.confidence_delta is not None
        assert msg.confidence_delta.proposed == 0.6

    def test_endorse_succeeds(self):
        msg = _msg(MessageIntent.ENDORSE, "AMI")
        assert msg.intent == MessageIntent.ENDORSE
