"""Run this script from the backend directory to apply the migration:
    cd backend
    python migrate_sessions.py
"""
import asyncio
import sys
sys.path.insert(0, ".")

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import get_settings


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        for stmt in [
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS session_summary TEXT",
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS conversation_json JSONB",
        ]:
            try:
                await conn.execute(text(stmt))
                print(f"[migrate] ✓ {stmt}")
            except Exception as e:
                print(f"[migrate] ⚠ {stmt}: {e}")

    await engine.dispose()
    print("[migrate] Done!")


if __name__ == "__main__":
    asyncio.run(main())
