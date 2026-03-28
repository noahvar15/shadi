"""Shared pytest helpers."""

from __future__ import annotations

import importlib
import os

import pytest

# Not a placeholder per api.config._PLACEHOLDER_API_SECRETS — keeps Settings() loadable in tests.
_PYTEST_API_SECRET = "pytest-api-secret-key-not-for-production-use"

# So modules imported at collection time (e.g. ``tasks.worker``) can call ``get_settings()`` safely.
os.environ.setdefault("API_SECRET_KEY", _PYTEST_API_SECRET)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:9/nope")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:9/0")


@pytest.fixture(autouse=True)
def _pytest_api_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure API_SECRET_KEY is set for any test that loads Settings."""
    monkeypatch.setenv("API_SECRET_KEY", _PYTEST_API_SECRET)


def reload_api_modules() -> None:
    """Reload API package so tests get fresh FastAPI routes and Settings cache."""
    import api.config as api_config
    import api.deps as api_deps
    import api.main as api_main
    import api.routes.cases as api_cases
    import api.routes.reports as api_reports

    importlib.reload(api_config)
    importlib.reload(api_deps)
    importlib.reload(api_cases)
    importlib.reload(api_reports)
    importlib.reload(api_main)
