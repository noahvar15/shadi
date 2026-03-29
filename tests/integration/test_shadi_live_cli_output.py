"""Live inference smoke: real Ollama (incl. Meditron) when ``--live-inference`` is passed."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNER = _REPO_ROOT / "tests" / "integration" / "run_live_cli.py"


@pytest.mark.integration
def test_live_multi_agent_pipeline_cli_output(request: pytest.FixtureRequest) -> None:
    """Spawns a fresh interpreter with MOCK_LLM=false so config/agents load correctly."""
    if not request.config.getoption("--live-inference"):
        pytest.skip("Pass --live-inference to run against real Ollama (slow, needs services).")

    env = {**os.environ, "MOCK_LLM": "false"}
    proc = subprocess.run(
        [sys.executable, str(_RUNNER)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=900,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, f"stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}"
    out = proc.stdout
    assert "SHADI — multi-agent differential" in out
    assert "Ranked differential" in out
    assert "Consensus level" in out
    assert "Safety veto" in out
    assert "(mock)" not in out, "Expected live inference, but output still contains (mock)"
