"""Run the full Shadi orchestrator and print the CLI report to stdout.

Usage (repo root):

    python3 -m tools.shadi_run_case_cli
    python3 -m tools.shadi_run_case_cli --triage-text "Chest pain x2h, diaphoretic." --chief-complaint "Chest pain"
    python3 -m tools.shadi_run_case_cli --live   # real Ollama + Postgres (see .env)

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
    """Use project venv when user runs ``python3 -m tools...`` without activating it.

    Do not compare ``Path(sys.executable).resolve()`` to ``.venv/bin/python``:
    the venv's ``python`` often symlinks to the system interpreter, so both
    paths resolve to the same file and re-exec would be skipped incorrectly.
    ``sys.prefix`` correctly identifies an active venv.
    """
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
        description="Run the full Shadi pipeline (intake path optional) and print the report.",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="Use real inference (MOCK_LLM=false); needs Ollama, Postgres, and other models per .env",
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
    p.add_argument("--patient-id", default="cli-demo-patient", help="Patient id for bundle or demo case")
    p.add_argument("--encounter-id", default="cli-demo-encounter", help="Encounter id for bundle or demo case")
    p.add_argument(
        "--skip-live-preflight",
        action="store_true",
        help="With --live: do not check Postgres / Ollama models before starting (may fail mid-run)",
    )
    return p.parse_args()


args = _parse_args()
os.environ["MOCK_LLM"] = "false" if args.live else "true"

if args.live and not args.skip_live_preflight:
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


async def _run() -> None:
    case = _case_for_cli(args)
    report = await Orchestrator().run(case)
    print(format_shadi_cli_report(case, report))


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
