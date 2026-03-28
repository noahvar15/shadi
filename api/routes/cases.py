"""Case intake routes (backend #32).

DEP-1: full ``CaseObject.from_fhir_bundle`` depends on Noah #28 normalizer contract;
``SHADI_STUB_CASE_INTAKE=1`` keeps the route testable without a valid FHIR bundle.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agents.schemas import CaseObject
from api.config import Settings, get_settings
from api.deps import ArqDep, PoolDep
from shadi_fhir.exceptions import FHIRValidationError

router = APIRouter()


class CaseQueuedResponse(BaseModel):
    case_id: str
    status: Literal["queued"] = "queued"


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
        except FHIRValidationError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO cases (id, status, case_json)
            VALUES ($1, $2, $3::jsonb)
            """,
            case.case_id,
            "queued",
            case.model_dump(mode="json"),
        )

    await arq_redis.enqueue_job(
        "tasks.pipeline.run_diagnostic_pipeline",
        str(case.case_id),
        _queue_name=settings.intake_queue,
    )

    return CaseQueuedResponse(case_id=str(case.case_id), status="queued")
