"""Patient search route.

Decision: Query cases table for real mode instead of a dedicated patients table.
Why: No separate patients table exists yet; avoids schema migration for MVP.
Alternatives: Dedicated patients table with proper FHIR Patient resources.
Tradeoffs: Only returns patients who already have cases; new patients not discoverable.
Unknowns: When FHIR MCP patient search is live, this route should delegate to it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.config import Settings, get_settings
from api.deps import PoolDep

router = APIRouter()


class PatientSearchResult(BaseModel):
    patient_id: str
    patient_name: str
    dob: str | None = None


DEMO_PATIENTS = [
    PatientSearchResult(
        patient_id="PT-DEMO-001",
        patient_name="Maria Gonzalez",
        dob="1978-04-15",
    ),
    PatientSearchResult(
        patient_id="PT-DEMO-002",
        patient_name="James Okafor",
        dob="1955-09-22",
    ),
    PatientSearchResult(
        patient_id="PT-DEMO-003",
        patient_name="Helen Park",
        dob="1990-03-07",
    ),
    PatientSearchResult(
        patient_id="PT-DEMO-004",
        patient_name="Robert Chen",
        dob="1963-11-30",
    ),
    PatientSearchResult(
        patient_id="PT-DEMO-005",
        patient_name="Angela Torres",
        dob="2001-07-19",
    ),
]


@router.get("/search")
async def search_patients(
    name: str,
    pool: PoolDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[PatientSearchResult]:
    query = name.strip()
    if len(query) < 2:
        return []

    if settings.stub_patient_search:
        query_lower = query.lower()
        return [
            patient
            for patient in DEMO_PATIENTS
            if query_lower in patient.patient_name.lower()
        ][:10]

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (patient_id) patient_id, patient_name
            FROM (
                SELECT
                    case_json->>'patient_id' AS patient_id,
                    case_json->>'patient_name' AS patient_name
                FROM cases
                WHERE case_json->>'patient_name' ILIKE $1
            ) sub
            WHERE patient_id IS NOT NULL AND patient_name IS NOT NULL
            LIMIT 10
            """,
            f"%{query}%",
        )

    return [
        PatientSearchResult(
            patient_id=row["patient_id"],
            patient_name=row["patient_name"],
            dob=None,
        )
        for row in rows
    ]
