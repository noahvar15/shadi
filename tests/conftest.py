"""Shared pytest helpers."""

from __future__ import annotations

import importlib


def reload_api_modules() -> None:
    """Reload API package so tests get fresh FastAPI routes and Settings cache."""
    import api.config as api_config
    import api.main as api_main
    import api.routes.cases as api_cases
    import api.routes.reports as api_reports

    importlib.reload(api_config)
    importlib.reload(api_cases)
    importlib.reload(api_reports)
    importlib.reload(api_main)
