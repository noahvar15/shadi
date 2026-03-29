"""Case intake routes (backend #32).

DEP-1: full ``CaseObject.from_fhir_bundle`` depends on Noah #28 normalizer contract;
``SHADI_STUB_CASE_INTAKE=1`` keeps the route testable without a valid FHIR bundle.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError

from agents.schemas import CaseObject
from api.config import Settings, get_settings
from api.deps import ArqDep, PoolDep
from shadi_fhir.exceptions import FHIRValidationError
from shadi_fhir.normalizer import FHIRNormalizer
from shadi_fhir.triage_bundle import build_triage_bundle

router = APIRouter()
logger = structlog.get_logger()


class CaseQueuedResponse(BaseModel):
    case_id: str
    status: Literal["queued"] = "queued"


class CaseSummary(BaseModel):
    case_id: str
    patient_id: str
    patient_name: str | None = None
    status: str
    created_at: str
    chief_complaint: str | None = None


class NurseIntakePayload(BaseModel):
    chief_complaint: str
    patient_stub_id: str | None = None
    patient_name: str | None = None


class FeedbackPayload(BaseModel):
    vote: Literal["up", "down"] | None = None
    note: str | None = None


class FeedbackResponse(BaseModel):
    ok: bool = True


@router.get("")
async def list_cases(pool: PoolDep) -> list[CaseSummary]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, status, case_json, created_at
            FROM cases
            ORDER BY created_at DESC
            LIMIT 100
            """,
        )
    results: list[CaseSummary] = []
    for row in rows:
        case_data: dict[str, Any] = {}
        if row["case_json"]:
            try:
                case_data = json.loads(row["case_json"]) if isinstance(row["case_json"], str) else row["case_json"]
            except (json.JSONDecodeError, TypeError):
                logger.warning("cases.case_json_decode_failed", case_id=str(row["id"]))
        results.append(
            CaseSummary(
                case_id=str(row["id"]),
                patient_id=case_data.get("patient_id", "unknown"),
                patient_name=case_data.get("patient_name"),
                status=row["status"],
                created_at=row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
                chief_complaint=case_data.get("chief_complaint"),
            )
        )
    return results


@router.get("/{case_id}")
async def get_case(case_id: UUID, pool: PoolDep) -> CaseSummary:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, status, case_json, created_at FROM cases WHERE id = $1",
            case_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")
    case_data: dict[str, Any] = {}
    if row["case_json"]:
        try:
            case_data = json.loads(row["case_json"]) if isinstance(row["case_json"], str) else row["case_json"]
        except (json.JSONDecodeError, TypeError):
            logger.warning("cases.case_json_decode_failed", case_id=str(case_id))
    return CaseSummary(
        case_id=str(row["id"]),
        patient_id=case_data.get("patient_id", "unknown"),
        patient_name=case_data.get("patient_name"),
        status=row["status"],
        created_at=row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
        chief_complaint=case_data.get("chief_complaint"),
    )


@router.post("/intake")
async def create_case_intake(
    payload: NurseIntakePayload,
    pool: PoolDep,
    arq_redis: ArqDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> CaseQueuedResponse:
    """Accept the nurse triage form and enqueue the diagnostic pipeline.

    Builds a FHIR R4 Bundle from the triage text via ``build_triage_bundle``,
    then normalises it through ``FHIRNormalizer`` — the same path as the live
    EHR subscription, so intake and FHIR-push produce identical ``CaseObject``
    shapes.
    """
    patient_id = payload.patient_stub_id or "stub"
    fhir_bundle = build_triage_bundle(
        patient_id=patient_id,
        encounter_id="enc-intake",
        triage_text=payload.chief_complaint,
        chief_complaint=payload.chief_complaint,
    )
    try:
        case = FHIRNormalizer().bundle_to_case(fhir_bundle)
    except (FHIRValidationError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Persist patient_name alongside the CaseObject in case_json.
    case_dict = case.model_dump(mode="json")
    if payload.patient_name:
        case_dict["patient_name"] = payload.patient_name

    case_json_str = json.dumps(case_dict)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO cases (id, status, case_json)
            VALUES ($1, $2, $3::jsonb)
            """,
            case.case_id,
            "pending_enqueue",
            case_json_str,
        )

    try:
        await arq_redis.enqueue_job(
            "run_diagnostic_pipeline",
            str(case.case_id),
            _queue_name=settings.intake_queue,
        )
    except Exception as exc:
        logger.error("cases.enqueue_failed", case_id=str(case.case_id), err=str(exc), exc_info=True)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE cases
                SET status = $2, error_message = $3, updated_at = NOW()
                WHERE id = $1 AND status = 'pending_enqueue'
                """,
                case.case_id,
                "enqueue_failed",
                "enqueue_failed",
            )
        raise HTTPException(
            status_code=503,
            detail="Unable to queue diagnostic job; try again later.",
        ) from exc

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE cases SET status = $2, updated_at = NOW()
            WHERE id = $1 AND status = 'pending_enqueue'
            """,
            case.case_id,
            "queued",
        )

    return CaseQueuedResponse(case_id=str(case.case_id), status="queued")


@router.post("")
async def create_case(
    bundle: dict[str, Any],
    pool: PoolDep,
    arq_redis: ArqDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> CaseQueuedResponse:
    if settings.stub_case_intake:
        case = CaseObject(
            patient_id="stub",
            encounter_id="stub-encounter",
            chief_complaint="",
            triage_notes_raw="",
        )
    else:
        try:
            case = CaseObject.from_fhir_bundle(bundle)
        except (FHIRValidationError, ValidationError) as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    case_json_str = json.dumps(case.model_dump(mode="json"))
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO cases (id, status, case_json)
            VALUES ($1, $2, $3::jsonb)
            """,
            case.case_id,
            "pending_enqueue",
            case_json_str,
        )

    try:
        await arq_redis.enqueue_job(
            "run_diagnostic_pipeline",
            str(case.case_id),
            _queue_name=settings.intake_queue,
        )
    except Exception as exc:
        logger.error("cases.enqueue_failed", case_id=str(case.case_id), err=str(exc), exc_info=True)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE cases
                SET status = $2, error_message = $3, updated_at = NOW()
                WHERE id = $1 AND status = 'pending_enqueue'
                """,
                case.case_id,
                "enqueue_failed",
                "enqueue_failed",
            )
        raise HTTPException(
            status_code=503,
            detail="Unable to queue diagnostic job; try again later.",
        ) from exc

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE cases SET status = $2, updated_at = NOW()
            WHERE id = $1 AND status = 'pending_enqueue'
            """,
            case.case_id,
            "queued",
        )

    return CaseQueuedResponse(case_id=str(case.case_id), status="queued")


@router.post("/{case_id}/feedback")
async def submit_feedback(
    case_id: UUID,
    payload: FeedbackPayload,
    pool: PoolDep,
) -> FeedbackResponse:
    """Record doctor thumbs-up / thumbs-down on a triage case."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE cases
            SET feedback = $2, feedback_note = $3, updated_at = NOW()
            WHERE id = $1
            """,
            case_id,
            payload.vote,
            payload.note,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Case not found")
    return FeedbackResponse(ok=True)
