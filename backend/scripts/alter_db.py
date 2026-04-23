"""
Database migration — add new User columns for profile & Google OAuth.

Run this script ONCE after pulling the model changes:
    cd backend
    python -m scripts.alter_db

It uses ALTER TABLE ... ADD COLUMN IF NOT EXISTS (PostgreSQL 9.6+)
so it's safe to run multiple times — it will skip columns that
already exist.
"""

import asyncio
from sqlalchemy import text
from app.services.database import engine


ALTER_STATEMENTS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(100) DEFAULT '';",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(100) DEFAULT '';",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(20) NOT NULL DEFAULT 'email';",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE;",
    "CREATE INDEX IF NOT EXISTS idx_users_google_id ON users (google_id);",
]


async def main():
    print("[migrate] Running ALTER TABLE statements...")
    async with engine.begin() as conn:
        for stmt in ALTER_STATEMENTS:
            try:
                await conn.execute(text(stmt))
                print(f"  ✓ {stmt[:60]}...")
            except Exception as e:
                print(f"  ⚠ Skipped: {e}")
    print("[migrate] Done. New columns are ready.")


if __name__ == "__main__":
    asyncio.run(main())
