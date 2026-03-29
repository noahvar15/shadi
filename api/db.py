"""Async PostgreSQL pool and schema for case intake / diagnostic reports.

Status lifecycle (single row per ``CaseObject``)::

    pending_enqueue → queued | enqueue_failed
    queued → processing → complete

``error_message`` holds enqueue failures or orchestrator traceback text (see ``tasks/pipeline``).
"""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger()

# Keep in sync with CHECK constraint and with api/routes/cases.py + tasks/pipeline.py
VALID_CASE_STATUSES: tuple[str, ...] = (
    "pending_enqueue",
    "enqueue_failed",
    "queued",
    "processing",
    "complete",
)

_CHECK_VALUES_SQL = ", ".join(f"'{s}'" for s in VALID_CASE_STATUSES)


def _asyncpg_dsn(database_url: str) -> str:
    """Return a DSN string asyncpg accepts (strip SQLAlchemy-style ``+asyncpg``)."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def init_pool(database_url: str) -> asyncpg.Pool:
    """Open a pool and run ``ensure_schema``; close the pool if schema setup fails."""
    pool = await asyncpg.create_pool(_asyncpg_dsn(database_url), min_size=1, max_size=10)
    try:
        await ensure_schema(pool)
    except Exception:
        await pool.close()
        raise
    return pool


async def ensure_schema(pool: asyncpg.Pool) -> None:
    """Create core tables and apply idempotent upgrades (safe on every process start)."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id UUID PRIMARY KEY,
                status VARCHAR(32) NOT NULL,
                case_json JSONB NOT NULL,
                report_json JSONB,
                error_message TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cases_status ON cases (status)",
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases (created_at DESC)",
        )

        # Constraint: duplicate-safe under concurrent ensure_schema (no pg_constraint TOCTOU).
        # _CHECK_VALUES_SQL is built only from VALID_CASE_STATUSES literals.
        await conn.execute(  # noqa: S608
            f"""
            DO $$
            BEGIN
              ALTER TABLE public.cases ADD CONSTRAINT cases_status_check
                CHECK (status IN ({_CHECK_VALUES_SQL}));
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END
            $$;
            """
        )

        await conn.execute("""
            ALTER TABLE public.cases
            ADD COLUMN IF NOT EXISTS patient_id TEXT
            GENERATED ALWAYS AS ((case_json->>'patient_id')) STORED;
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cases_patient_id ON cases (patient_id)
            WHERE patient_id IS NOT NULL;
        """)

        await conn.execute("""
            CREATE OR REPLACE FUNCTION shadi_touch_cases_updated_at()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
              NEW.updated_at := NOW();
              RETURN NEW;
            END;
            $$;
        """)

        await conn.execute("""
            CREATE OR REPLACE TRIGGER cases_touch_updated_at
              BEFORE UPDATE ON public.cases
              FOR EACH ROW
              EXECUTE FUNCTION shadi_touch_cases_updated_at();
        """)

    logger.info("db.schema.ready")


async def close_pool(pool: asyncpg.Pool | None) -> None:
    """Close the pool if present (no-op for ``None``)."""
    if pool is not None:
        await pool.close()
