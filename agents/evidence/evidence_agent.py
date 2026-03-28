"""Evidence grounding agent.

Two-phase pipeline per ADR-002:

1. **Retrieval** — embed each specialist diagnosis display string with
   ``nomic-embed-text`` (Ollama ``/api/embeddings``), then run a pgvector
   cosine-distance query against the ``evidence`` table.

2. **Claim evaluation** — for every retrieved passage, ask ``meditron:70b``
   (vLLM) whether the passage SUPPORTS, REFUTES, or is NEUTRAL toward the
   candidate diagnosis. Only SUPPORTS passages become ``EvidenceCitation``
   objects attached to ``DiagnosisCandidate.supporting_evidence``.

Graceful degradation
--------------------
If the pgvector table is empty (or the similarity threshold returns no rows)
the agent logs a warning and returns the diagnoses unchanged — no citations,
no crash.

Mock mode
---------
When ``settings.MOCK_LLM`` is ``True`` (the default for local development)
the entire embedding + DB + claim-eval loop is skipped. The method returns an
``EvidenceResult`` with the input diagnoses unmodified, identical to the
empty-table degradation path.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

import httpx
import structlog

if TYPE_CHECKING:
    import asyncpg as asyncpg_t

from agents._llm import call_chat
from agents.base import BaseAgent
from agents.schemas import (
    CaseObject,
    DiagnosisCandidate,
    EvidenceCitation,
    EvidenceResult,
    SpecialistResult,
)
from config import settings

logger = structlog.get_logger()

_CLAIM_EVAL_SYSTEM = """\
You are a clinical evidence reviewer. Given a passage from a medical guideline
or PubMed abstract and a proposed diagnosis, decide whether the passage
supports or contradicts the diagnosis.

Reply with ONLY valid JSON containing exactly two keys:
  "verdict"     : one of "SUPPORTS", "REFUTES", or "NEUTRAL"
  "explanation" : one sentence justifying your verdict
"""

_CLAIM_EVAL_USER = """\
Passage:
{excerpt}

Source: {source}

Proposed diagnosis: {diagnosis_display}

Does this passage support the claim that "{diagnosis_display}" is the correct
diagnosis for this patient? Answer SUPPORTS / REFUTES / NEUTRAL.
"""

# pgvector cosine-distance threshold: passages with distance ≥ this value are
# considered too dissimilar to be useful evidence.
_SIMILARITY_THRESHOLD = 0.4
_MAX_PASSAGES = 5


class EvidenceAgent(BaseAgent[EvidenceResult]):
    """Evidence grounding using nomic-embed-text retrieval + meditron:70b claim eval."""

    name = "evidence"
    domain = "evidence"
    model = "nomic-embed-text"  # primary: embedding via Ollama
    inference_url = settings.OLLAMA_BASE_URL

    # ---------------------------------------------------------------------------
    # Public interface — overrides BaseAgent.run to accept specialist_results
    # ---------------------------------------------------------------------------

    async def run(
        self,
        case: CaseObject,
        specialist_results: list[SpecialistResult] | None = None,
    ) -> EvidenceResult:
        """Run evidence grounding and return an ``EvidenceResult``.

        Parameters
        ----------
        case:
            The patient case.
        specialist_results:
            Required. Output from all specialist agents. Passing ``None``
            raises ``ValueError`` immediately so callers get a clear error
            rather than a silent no-op.
        """
        if specialist_results is None:
            raise ValueError(
                "EvidenceAgent.run requires specialist_results; "
                "call agent.run(case, specialist_results) not agent.run(case)"
            )
        start = time.monotonic()
        log = logger.bind(agent=self.name, domain=self.domain, model=self.model)
        log.info("agent.start", case_id=case.case_id)
        try:
            result = await self.reason(case, specialist_results)
            elapsed_ms = (time.monotonic() - start) * 1000
            log.info("agent.complete", case_id=case.case_id, elapsed_ms=round(elapsed_ms, 1))
            return result
        except Exception:
            elapsed_ms = (time.monotonic() - start) * 1000
            log.exception("agent.error", case_id=case.case_id, elapsed_ms=round(elapsed_ms, 1))
            raise

    async def reason(  # type: ignore[override]
        self,
        case: CaseObject,
        specialist_results: list[SpecialistResult],
    ) -> EvidenceResult:
        """Ground each specialist diagnosis against the pgvector evidence corpus.

        Parameters
        ----------
        case:
            The patient case (used for ``case_id`` and logging context only at
            this stage — the diagnoses themselves come from ``specialist_results``).
        specialist_results:
            Output from all specialist agents. Each ``SpecialistResult`` carries
            a list of ``DiagnosisCandidate`` objects to be grounded.

        Returns
        -------
        EvidenceResult
            All diagnoses from every specialist result, with
            ``supporting_evidence`` populated for candidates where at least one
            SUPPORTS passage was found.
        """
        log = logger.bind(agent=self.name, case_id=case.case_id)

        all_diagnoses: list[DiagnosisCandidate] = [
            diagnosis
            for sr in specialist_results
            for diagnosis in sr.diagnoses
        ]

        if settings.MOCK_LLM:
            return EvidenceResult(
                agent_name=self.name,
                case_id=case.case_id,
                grounded_diagnoses=all_diagnoses,
            )

        import asyncpg  # lazy: not available in all dev environments

        raw_dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

        conn: asyncpg_t.Connection = await asyncpg.connect(raw_dsn)
        try:
            for diagnosis in all_diagnoses:
                await self._ground_diagnosis(diagnosis, conn, log)
        finally:
            await conn.close()

        return EvidenceResult(
            agent_name=self.name,
            case_id=case.case_id,
            grounded_diagnoses=all_diagnoses,
        )

    # ---------------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------------

    async def _ground_diagnosis(
        self,
        diagnosis: DiagnosisCandidate,
        conn: Any,
        log: Any,
    ) -> None:
        """Embed one diagnosis, query pgvector, evaluate claims, attach citations."""
        embedding = await self._embed(diagnosis.display)
        passages = await self._query_pgvector(embedding, conn)

        if not passages:
            log.warning(
                "evidence.no_passages",
                diagnosis=diagnosis.display,
                threshold=_SIMILARITY_THRESHOLD,
            )
            return

        for passage in passages:
            verdict = await self._evaluate_claim(
                excerpt=passage["excerpt"],
                source=passage["source"],
                diagnosis_display=diagnosis.display,
            )
            if verdict == "SUPPORTS":
                diagnosis.supporting_evidence.append(
                    EvidenceCitation(
                        source=passage["source"],
                        excerpt=passage["excerpt"],
                        relevance_score=float(passage.get("distance", 0.0)),
                    )
                )

    async def _embed(self, text: str) -> list[float]:
        """Return the nomic-embed-text embedding vector for *text*.

        Calls the native Ollama ``/api/embeddings`` endpoint (not the OpenAI
        ``/v1`` shim, which does not expose embedding generation for
        nomic-embed-text).
        """
        ollama_root = settings.OLLAMA_BASE_URL.removesuffix("/v1")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{ollama_root}/api/embeddings",
                json={"model": self.model, "prompt": text},
            )
            resp.raise_for_status()
            return list(resp.json()["embedding"])

    async def _query_pgvector(
        self,
        embedding: list[float],
        conn: Any,
    ) -> list[dict[str, Any]]:
        """Query the pgvector ``evidence`` table for nearest-neighbour passages.

        Returns up to ``_MAX_PASSAGES`` rows whose cosine distance to
        *embedding* is below ``_SIMILARITY_THRESHOLD``.
        """
        rows = await conn.fetch(
            """
            SELECT excerpt, source, (embedding <-> $1::vector) AS distance
            FROM evidence
            WHERE embedding <-> $1::vector < $2
            ORDER BY embedding <-> $1::vector
            LIMIT $3
            """,
            json.dumps(embedding),
            _SIMILARITY_THRESHOLD,
            _MAX_PASSAGES,
        )
        return [dict(r) for r in rows]

    async def _evaluate_claim(
        self,
        excerpt: str,
        source: str,
        diagnosis_display: str,
    ) -> str:
        """Ask meditron:70b whether *excerpt* supports *diagnosis_display*.

        Returns one of ``"SUPPORTS"``, ``"REFUTES"``, or ``"NEUTRAL"``.
        Defaults to ``"NEUTRAL"`` if the response cannot be parsed.
        """
        user_content = _CLAIM_EVAL_USER.format(
            excerpt=excerpt,
            source=source,
            diagnosis_display=diagnosis_display,
        )
        messages = [
            {"role": "system", "content": _CLAIM_EVAL_SYSTEM},
            {"role": "user", "content": user_content},
        ]
        raw = await call_chat(
            settings.VLLM_BASE_URL,
            "meditron:70b",
            messages,
            response_format={"type": "json_object"},
            mock_domain=self.domain,
        )
        try:
            payload: dict[str, Any] = json.loads(raw)
            verdict = str(payload.get("verdict", "NEUTRAL")).upper()
            if verdict not in {"SUPPORTS", "REFUTES", "NEUTRAL"}:
                return "NEUTRAL"
            return verdict
        except (json.JSONDecodeError, KeyError):
            return "NEUTRAL"
