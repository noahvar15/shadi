"""Robust parser for specialist agent model outputs.

meditron:70b does not always follow JSON format instructions perfectly.
Common failure modes this module handles:

  1. Output wrapped in markdown fences (```json ... ```)
  2. Flat diagnosis object instead of {"diagnoses": [...], "reasoning_trace": "..."}
  3. reasoning_trace returned as list, null, or non-string type
  4. Field-name variations: snomed_id → snomed_code, next_step → next_steps
  5. Extra/unknown fields that should be silently dropped
  6. Partial JSON parse failures for individual diagnoses
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog

from agents.schemas import DiagnosisCandidate, SpecialistResult

logger = structlog.get_logger()

_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)

_FIELD_ALIASES: dict[str, str] = {
    "snomed_id": "snomed_code",
    "snomedCode": "snomed_code",
    "snomedcode": "snomed_code",
    "next_step": "next_steps",
    "nextSteps": "next_steps",
    "nextsteps": "next_steps",
    "nextstep": "next_steps",
}


def _strip_fences(raw: str) -> str:
    m = _FENCE_RE.search(raw)
    return m.group(1).strip() if m else raw.strip()


def _coerce_string(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        return "\n".join(str(item) for item in val) if val else ""
    return str(val)


def _normalize_diagnosis(raw_d: dict[str, Any]) -> dict[str, Any]:
    """Apply field-name aliases and coerce types for DiagnosisCandidate."""
    normalized: dict[str, Any] = {}
    for k, v in raw_d.items():
        target_key = _FIELD_ALIASES.get(k, k)
        if target_key == "next_steps":
            if isinstance(v, list):
                flat: list[str] = []
                for item in v:
                    if isinstance(item, list):
                        flat.extend(str(x) for x in item)
                    else:
                        flat.append(str(item))
                v = flat
            elif isinstance(v, str):
                v = [v]
            else:
                v = []
        if target_key == "flags" and not isinstance(v, list):
            v = [str(v)] if v else []
        if target_key == "confidence":
            try:
                v = float(v)
                v = max(0.0, min(1.0, v))
            except (TypeError, ValueError):
                v = 0.5
        if target_key == "rank":
            try:
                v = int(v)
            except (TypeError, ValueError):
                v = 0
        normalized[target_key] = v
    return normalized


def _extract_diagnoses_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Find the diagnoses array whether nested or flat."""
    if "diagnoses" in payload and isinstance(payload["diagnoses"], list):
        return payload["diagnoses"]

    if "diagnosis" in payload and isinstance(payload["diagnosis"], list):
        return payload["diagnosis"]

    has_dx_keys = {"display", "confidence"}.issubset(payload.keys())
    if has_dx_keys:
        return [payload]

    for key, val in payload.items():
        if isinstance(val, list) and val and isinstance(val[0], dict):
            if any(k in val[0] for k in ("display", "confidence", "rank")):
                return val

    return []


def parse_specialist_response(
    raw: str,
    *,
    agent_name: str,
    domain: str,
    case_id: Any,
    log_path: str | None = None,
) -> SpecialistResult:
    """Parse raw LLM output into a SpecialistResult, tolerating model quirks."""
    log = logger.bind(agent=agent_name, domain=domain)

    cleaned = _strip_fences(raw)

    try:
        payload: dict = json.loads(cleaned)
    except json.JSONDecodeError:
        last_brace = cleaned.rfind("}")
        if last_brace > 0:
            try:
                payload = json.loads(cleaned[: last_brace + 1])
            except json.JSONDecodeError:
                log.error("specialist.json_parse_failed", raw_preview=raw[:300])
                _log_to_file(log_path, agent_name, "json_parse_failed", {"raw_preview": raw[:500]})
                return SpecialistResult(
                    agent_name=agent_name,
                    case_id=case_id,
                    domain=domain,
                    diagnoses=[],
                    reasoning_trace=f"Model returned unparseable output: {raw[:200]}",
                )
        else:
            log.error("specialist.json_parse_failed", raw_preview=raw[:300])
            _log_to_file(log_path, agent_name, "json_parse_failed", {"raw_preview": raw[:500]})
            return SpecialistResult(
                agent_name=agent_name,
                case_id=case_id,
                domain=domain,
                diagnoses=[],
                reasoning_trace=f"Model returned unparseable output: {raw[:200]}",
            )

    raw_diagnoses = _extract_diagnoses_list(payload)
    reasoning = _coerce_string(payload.get("reasoning_trace", ""))

    if not reasoning and "reasoning" in payload:
        reasoning = _coerce_string(payload["reasoning"])

    diagnoses: list[DiagnosisCandidate] = []
    for i, raw_d in enumerate(raw_diagnoses):
        try:
            if not isinstance(raw_d, dict):
                continue
            norm = _normalize_diagnosis(raw_d)
            if "rank" not in norm or norm["rank"] == 0:
                norm["rank"] = i + 1
            if "display" not in norm:
                continue
            dx = DiagnosisCandidate(**{
                k: v for k, v in norm.items()
                if k in DiagnosisCandidate.model_fields
            })
            diagnoses.append(dx)
        except Exception as exc:
            log.warning("specialist.diagnosis_parse_skip", index=i, error=str(exc))

    _log_to_file(log_path, agent_name, "parsed_result", {
        "raw_preview": raw[:500],
        "diagnoses_count": len(diagnoses),
        "diagnoses": [d.model_dump() for d in diagnoses],
        "reasoning_preview": reasoning[:200],
    })

    return SpecialistResult(
        agent_name=agent_name,
        case_id=case_id,
        domain=domain,
        diagnoses=diagnoses,
        reasoning_trace=reasoning,
    )


def _log_to_file(path: str | None, agent: str, message: str, data: dict) -> None:
    if not path:
        return
    import time
    entry = json.dumps({
        "sessionId": "4f5ee4",
        "location": f"agents/specialists/_parse.py:{agent}",
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
        "hypothesisId": "H1-H4",
        "runId": "pre-fix",
    })
    try:
        with open(path, "a") as f:
            f.write(entry + "\n")
    except OSError:
        pass
