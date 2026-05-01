-- Migration: Transform BYOK from plan to feature toggle
-- Date: 2026-05-01
-- Description: Add byok_enabled column and migrate existing BYOK users

BEGIN;

-- Step 1: Add byok_enabled column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'byok_enabled'
    ) THEN
        ALTER TABLE users ADD COLUMN byok_enabled BOOLEAN DEFAULT FALSE NOT NULL;
        RAISE NOTICE 'Added byok_enabled column';
    ELSE
        RAISE NOTICE 'byok_enabled column already exists';
    END IF;
END
$$;

-- Step 2: Migrate existing BYOK users (preserve their access)
UPDATE users
SET byok_enabled = TRUE
WHERE plan = 'byok';

-- Step 3: Move BYOK users to Free plan (they share same lifetime quota)
UPDATE users
SET plan = 'free'
WHERE plan = 'byok';

-- Verification query
SELECT
    plan,
    byok_enabled,
    COUNT(*) as user_count
FROM users
GROUP BY plan, byok_enabled
ORDER BY plan;

COMMIT;

-- To rollback this migration:
-- BEGIN;
-- UPDATE users SET plan = 'byok' WHERE byok_enabled = TRUE AND plan = 'free';
-- ALTER TABLE users DROP COLUMN IF EXISTS byok_enabled;
-- COMMIT;
