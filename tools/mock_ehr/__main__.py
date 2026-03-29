"""Run: ``python -m tools.mock_ehr`` (default port 9001)."""

from __future__ import annotations

import os

import uvicorn

from tools.mock_ehr.app import app


def main() -> None:
    host = os.environ.get("MOCK_EHR_HOST", "0.0.0.0")
    port = int(os.environ.get("MOCK_EHR_PORT", "9001"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
