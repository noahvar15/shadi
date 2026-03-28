"""Tests for API track issue #33: report routes and diagnostic pipeline job."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from agents.schemas import CaseObject
from tests.conftest import reload_api_modules


@contextmanager
def _patched_app(monkeypatch: pytest.MonkeyPatch, mock_conn: AsyncMock):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:9/nope")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:9/0")
    monkeypatch.setenv("SHADI_STUB_CASE_INTAKE", "1")

    from api.config import get_settings

    get_settings.cache_clear()

    mock_pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield mock_conn

    mock_pool.acquire = _acquire
    mock_pool.close = AsyncMock()
    mock_arq = MagicMock()
    mock_arq.enqueue_job = AsyncMock()
    mock_arq.close = AsyncMock()

    with (
        patch("api.db.init_pool", AsyncMock(return_value=mock_pool)),
        patch("arq.create_pool", AsyncMock(return_value=mock_arq)),
        patch("api.db.close_pool", AsyncMock()),
    ):
        reload_api_modules()
        import api.main as api_main

        with TestClient(api_main.app) as client:
            yield client, mock_conn


def test_report_status_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    with _patched_app(monkeypatch, mock_conn) as (client, _):
        r = client.get(f"/reports/{uuid4()}/status")
    assert r.status_code == 404


def test_report_status_queued(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(
        return_value={"status": "queued", "error_message": None},
    )
    cid = uuid4()
    with _patched_app(monkeypatch, mock_conn) as (client, _):
        r = client.get(f"/reports/{cid}/status")
    assert r.status_code == 200
    assert r.json() == {"status": "queued", "error": None}


def test_get_report_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(
        return_value={"status": "queued", "report_json": None},
    )
    cid = uuid4()
    with _patched_app(monkeypatch, mock_conn) as (client, _):
        r = client.get(f"/reports/{cid}")
    assert r.status_code == 404


def test_get_report_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    cid = uuid4()
    payload = {
        "case_id": str(cid),
        "synthesized_at": "2026-03-28T12:00:00",
        "top_diagnoses": [],
        "vetoed_recommendations": [],
        "consensus_level": 0.0,
        "divergent_agents": [],
        "fhir_diagnostic_report_id": None,
    }
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(
        return_value={"status": "complete", "report_json": payload},
    )
    with _patched_app(monkeypatch, mock_conn) as (client, _):
        r = client.get(f"/reports/{cid}")
    assert r.status_code == 200
    assert r.json()["case_id"] == str(cid)


@pytest.mark.asyncio
async def test_run_diagnostic_pipeline_writes_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHADI_STUB_CASE_INTAKE", "1")
    case = CaseObject(
        patient_id="stub",
        encounter_id="stub-encounter",
        chief_complaint="",
        triage_notes_raw="",
    )
    cid = case.case_id
    case_payload = case.model_dump(mode="json")

    fetch_returns: list[dict] = [
        {"case_json": case_payload},
    ]
    conn = AsyncMock()

    async def fetchrow(*_a, **_k):
        if not fetch_returns:
            return None
        return fetch_returns.pop(0)

    conn.fetchrow = AsyncMock(side_effect=fetchrow)
    conn.execute = AsyncMock()

    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire

    from tasks.pipeline import run_diagnostic_pipeline

    await run_diagnostic_pipeline({"pool": pool}, str(case.case_id))

    assert conn.execute.await_count >= 2
    final_sql = str(conn.execute.await_args_list[-1].args[0])
    assert "report_json" in final_sql
    args = conn.execute.await_args_list[-1].args
    assert args[1] == cid
    assert args[3] == "complete"
    report_blob = args[2]
    if isinstance(report_blob, str):
        data = json.loads(report_blob)
    else:
        data = report_blob
    assert data["case_id"] == str(cid)
    assert args[4] is None
