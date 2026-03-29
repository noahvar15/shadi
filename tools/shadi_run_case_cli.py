"""Run the Shadi diagnostic pipeline — locally or via the API.

Usage (repo root):

    # Direct orchestrator (CLI output):
    python3 -m tools.shadi_run_case_cli
    python3 -m tools.shadi_run_case_cli --triage-text "Chest pain x2h, diaphoretic." --chief-complaint "Chest pain"
    python3 -m tools.shadi_run_case_cli --live   # real Ollama + Postgres (see .env)

    # Submit to the API (results appear on the dashboard):
    python3 -m tools.shadi_run_case_cli --api
    python3 -m tools.shadi_run_case_cli --api --api-url http://localhost:8000
    python3 -m tools.shadi_run_case_cli --api --triage-text "Severe headache, sudden onset"

If ``.venv`` exists, a bare ``python3`` invocation is **re-executed** with
``.venv/bin/python`` so project deps (pydantic, etc.) are on ``sys.path``.

``MOCK_LLM`` is set for this process **before** importing agents (default
``true``). Pass ``--live`` for a real run; requires services from ``.env``.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path


def _maybe_reexec_with_project_venv() -> None:
    """Use project venv when user runs ``python3 -m tools...`` without activating it."""
    root = Path(__file__).resolve().parents[1]
    venv_dir = (root / ".venv").resolve()
    venv_python = venv_dir / "bin" / "python"
    has_venv = venv_python.is_file()
    try:
        prefix_is_venv = Path(sys.prefix).resolve() == venv_dir
    except OSError:
        prefix_is_venv = False
    if not has_venv or prefix_is_venv:
        return
    argv = [str(venv_python), "-m", "tools.shadi_run_case_cli", *sys.argv[1:]]
    os.execv(str(venv_python), argv)


_maybe_reexec_with_project_venv()

if importlib.util.find_spec("pydantic") is None:
    print(
        "Missing dependencies (e.g. pydantic). From repo root run:\n"
        "  python3 -m venv .venv\n"
        "  .venv/bin/pip install -e '.[dev]'\n"
        "Then: python3 -m tools.shadi_run_case_cli",
        file=sys.stderr,
    )
    raise SystemExit(1)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the Shadi pipeline locally or submit to the API for dashboard output.",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="Use real inference (MOCK_LLM=false); needs Ollama, Postgres, and other models per .env",
    )
    p.add_argument(
        "--api",
        action="store_true",
        help="Submit to the Shadi API instead of running locally. Results appear on the dashboard.",
    )
    p.add_argument(
        "--api-url",
        default="http://localhost:8000",
        metavar="URL",
        help="Base URL for the Shadi API (default: http://localhost:8000)",
    )
    p.add_argument(
        "--dashboard-url",
        default="http://localhost:3000",
        metavar="URL",
        help="Dashboard URL for case links (default: http://localhost:3000)",
    )
    p.add_argument(
        "--triage-text",
        metavar="TEXT",
        help="Nurse triage narrative → FHIR bundle (LOINC 34109-9) → CaseObject, then pipeline",
    )
    p.add_argument(
        "--chief-complaint",
        metavar="TEXT",
        help="With --triage-text: sets encounter reason / chief complaint (default: derived from triage text)",
    )
    p.add_argument(
        "--patient-name",
        default="CLI Demo Patient",
        metavar="NAME",
        help="Patient display name (used with --api)",
    )
    p.add_argument("--patient-id", default="cli-demo-patient", help="Patient id for bundle or demo case")
    p.add_argument("--encounter-id", default="cli-demo-encounter", help="Encounter id for bundle or demo case")
    p.add_argument(
        "--skip-live-preflight",
        action="store_true",
        help="With --live: do not check Postgres / Ollama models before starting (may fail mid-run)",
    )
    p.add_argument(
        "--no-poll",
        action="store_true",
        help="With --api: submit and exit immediately without polling for results",
    )
    return p.parse_args()


args = _parse_args()

if not args.api:
    os.environ["MOCK_LLM"] = "false" if args.live else "true"

if args.live and not args.api and not args.skip_live_preflight:
    from tools.live_preflight import collect_live_preflight_issues

    fatal, warns = collect_live_preflight_issues()
    for w in warns:
        print(f"live preflight warning: {w}", file=sys.stderr)
    if fatal:
        for msg in fatal:
            print(f"live preflight error: {msg}", file=sys.stderr)
        print(
            "Fix the above, or re-run with --skip-live-preflight (runtime may still fail).",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _chief_complaint_text(a: argparse.Namespace) -> str:
    if a.triage_text:
        return a.triage_text
    return a.chief_complaint or "Chest pain and shortness of breath"


def _run_via_api(a: argparse.Namespace) -> None:
    """Submit a case to the API and optionally poll for results."""
    import json
    import time
    import urllib.request
    import urllib.error

    base = a.api_url.rstrip("/")
    complaint = _chief_complaint_text(a)

    payload = json.dumps({
        "chief_complaint": complaint,
        "patient_stub_id": a.patient_id,
        "patient_name": a.patient_name,
    }).encode()

    print(f"Submitting case to {base}/cases/intake ...")
    req = urllib.request.Request(
        f"{base}/cases/intake",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
    except urllib.error.URLError as exc:
        print(f"Failed to reach API: {exc}", file=sys.stderr)
        print(f"Is the API running at {base}?", file=sys.stderr)
        raise SystemExit(1)

    case_id = result["case_id"]
    dashboard = a.dashboard_url.rstrip("/")
    print(f"Case submitted: {case_id}")
    print(f"Dashboard:      {dashboard}/cases/{case_id}")
    print(f"Triage note:    {dashboard}/cases/{case_id}/triage")

    if a.no_poll:
        return

    print("\nPolling for pipeline completion...")
    terminal_statuses = {"complete", "failed", "enqueue_failed"}
    poll_count = 0
    while True:
        time.sleep(2)
        poll_count += 1
        try:
            with urllib.request.urlopen(f"{base}/reports/{case_id}") as resp:
                report = json.loads(resp.read())
        except urllib.error.URLError:
            print(f"  [{poll_count}] Waiting for API...", file=sys.stderr)
            continue

        status = report.get("status", "unknown")
        if status in terminal_statuses:
            print(f"\nPipeline {status}.")
            if status == "complete":
                diagnoses = report.get("top_diagnoses", [])
                if diagnoses:
                    print(f"\nTop {len(diagnoses)} diagnoses:")
                    for dx in diagnoses:
                        print(f"  {dx['rank']}. {dx['display']} (confidence: {dx['confidence']:.2f})")
                print(f"\nFull report on dashboard: {dashboard}/cases/{case_id}")
            elif report.get("error_message"):
                print(f"Error: {report['error_message'][:500]}", file=sys.stderr)
            break
        else:
            indicators = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            print(f"\r  {indicators[poll_count % len(indicators)]} Status: {status}...", end="", flush=True)


import asyncio  # noqa: E402

from agents.cli_output import format_shadi_cli_report  # noqa: E402
from agents.orchestrator.orchestrator import Orchestrator  # noqa: E402
from agents.schemas import CaseObject  # noqa: E402


def _case_for_cli(a: argparse.Namespace) -> CaseObject:
    if a.triage_text:
        from shadi_fhir.normalizer import FHIRNormalizer
        from shadi_fhir.triage_bundle import build_triage_bundle

        bundle = build_triage_bundle(
            patient_id=a.patient_id,
            encounter_id=a.encounter_id,
            triage_text=a.triage_text,
            chief_complaint=a.chief_complaint,
        )
        return FHIRNormalizer().bundle_to_case(bundle)
    return CaseObject(
        patient_id=a.patient_id,
        encounter_id=a.encounter_id,
        chief_complaint="Chest pain and shortness of breath",
        triage_notes_raw=(
            "55-year-old male with substernal pressure radiating to the jaw, "
            "diaphoretic, onset ~2 hours ago. History of hypertension."
        ),
    )


async def _run_local() -> None:
    case = _case_for_cli(args)
    report = await Orchestrator().run(case)
    print(format_shadi_cli_report(case, report))


def main() -> None:
    if args.api:
        _run_via_api(args)
    else:
        asyncio.run(_run_local())


if __name__ == "__main__":
    main()
