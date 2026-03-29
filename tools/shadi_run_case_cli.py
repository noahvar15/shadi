"""Run the full Shadi orchestrator (mock LLM by default) and print CLI output.

Usage (repo root):

    python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
    python3 -m tools.shadi_run_case_cli

If ``.venv`` exists, a bare ``python3`` invocation is **re-executed** with
``.venv/bin/python`` so project deps (pydantic, etc.) are on ``sys.path``.

This module sets ``MOCK_LLM=true`` for the process **before** importing agents,
so the demo runs without vLLM/Ollama even if ``.env`` has ``MOCK_LLM=false``.
For a live run, use the API + worker with real inference instead.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

# Must run before ``from agents...`` so ``config.settings`` is built with mock mode.
os.environ["MOCK_LLM"] = "true"


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

import asyncio  # noqa: E402

from agents.cli_output import format_shadi_cli_report  # noqa: E402
from agents.orchestrator.orchestrator import Orchestrator  # noqa: E402
from agents.schemas import CaseObject  # noqa: E402


def _demo_case() -> CaseObject:
    return CaseObject(
        patient_id="cli-demo-patient",
        encounter_id="cli-demo-encounter",
        chief_complaint="Chest pain and shortness of breath",
        triage_notes_raw=(
            "55-year-old male with substernal pressure radiating to the jaw, "
            "diaphoretic, onset ~2 hours ago. History of hypertension."
        ),
    )


async def _run() -> None:
    case = _demo_case()
    report = await Orchestrator().run(case)
    print(format_shadi_cli_report(case, report))


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
