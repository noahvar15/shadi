"""Async PostgreSQL pool and minimal schema for case intake / reports."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger()


def _asyncpg_dsn(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def init_pool(database_url: str) -> asyncpg.Pool:
    pool = await asyncpg.create_pool(_asyncpg_dsn(database_url), min_size=1, max_size=10)
    try:
        await ensure_schema(pool)
    except Exception:
        await pool.close()
        raise
    return pool


async def ensure_schema(pool: asyncpg.Pool) -> None:
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
    logger.info("db.schema.ready")


async def close_pool(pool: asyncpg.Pool | None) -> None:
    if pool is not None:
        await pool.close()
