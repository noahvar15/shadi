"""Shared data models used across all agents."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ─── Input ───────────────────────────────────────────────────────────────────


class ClinicalCode(BaseModel):
    system: str  # e.g. "http://snomed.info/sct"
    code: str
    display: str


class Medication(BaseModel):
    rxnorm_code: str
    name: str
    dose: str | None = None
    route: str | None = None


class Allergy(BaseModel):
    substance: str
    rxnorm_code: str | None = None
    reaction: str | None = None
    severity: str | None = None  # "mild" | "moderate" | "severe"


class Observation(BaseModel):
    loinc_code: str
    display: str
    value: str | float | None = None
    unit: str | None = None
    timestamp: datetime | None = None


class CaseObject(BaseModel):
    """Normalized patient case passed to all agents."""

    @classmethod
    def from_fhir_bundle(cls, bundle_json: dict[str, Any]) -> CaseObject:
        """Build a case from a FHIR R4 ``Bundle`` resource (parsed JSON dict)."""
        from shadi_fhir.normalizer import FHIRNormalizer

        return FHIRNormalizer().bundle_to_case(bundle_json)

    case_id: UUID = Field(default_factory=uuid4)
    patient_id: str
    encounter_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Structured from triage notes by the intake agent
    chief_complaint: str
    triage_notes_raw: str
    conditions: list[ClinicalCode] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)
    allergies: list[Allergy] = Field(default_factory=list)

    # Additional context
    age: int | None = None
    sex: str | None = None  # "male" | "female" | "other"


# ─── Output ──────────────────────────────────────────────────────────────────


class EvidenceCitation(BaseModel):
    source: str  # e.g. "PubMed:12345678" or "AHA-Guidelines-2024"
    excerpt: str
    relevance_score: float = Field(ge=0.0, le=1.0)


class DiagnosisCandidate(BaseModel):
    rank: int
    snomed_code: str | None = None
    display: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[EvidenceCitation] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)  # e.g. ["EVIDENCE_GAP"]


class AgentResult(BaseModel):
    """Base result type for all agents."""

    agent_name: str
    case_id: UUID
    produced_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SpecialistResult(AgentResult):
    """Result produced by a specialist agent."""

    domain: str
    diagnoses: list[DiagnosisCandidate] = Field(default_factory=list)
    reasoning_trace: str = ""


class VetoDecision(BaseModel):
    recommendation: str
    vetoed: bool
    reason: str | None = None
    contraindication_codes: list[str] = Field(default_factory=list)


class SafetyResult(AgentResult):
    """Result produced by the safety veto agent."""

    decisions: list[VetoDecision] = Field(default_factory=list)


class DifferentialReport(BaseModel):
    """Final synthesized output written as a FHIR DiagnosticReport."""

    case_id: UUID
    synthesized_at: datetime = Field(default_factory=datetime.utcnow)
    top_diagnoses: list[DiagnosisCandidate] = Field(default_factory=list)
    vetoed_recommendations: list[VetoDecision] = Field(default_factory=list)
    consensus_level: float = Field(ge=0.0, le=1.0, default=0.0)
    divergent_agents: list[str] = Field(default_factory=list)
    fhir_diagnostic_report_id: str | None = None
