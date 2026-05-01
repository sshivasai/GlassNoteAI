-- Migration: Add byok_enabled column to users table
-- Date: 2026-05-01
-- Description: Convert BYOK from a plan to a feature flag

-- Step 1: Add the byok_enabled column (default False)
ALTER TABLE users ADD COLUMN IF NOT EXISTS byok_enabled BOOLEAN DEFAULT FALSE;

-- Step 2: Migrate existing BYOK plan users
-- Set byok_enabled=TRUE for users currently on the BYOK plan
UPDATE users
SET byok_enabled = TRUE
WHERE plan = 'byok';

-- Step 3: Update BYOK users to free plan (or keep their previous paid plan if they had one)
-- Since BYOK was free and shares lifetime quota with free, migrate them to free
UPDATE users
SET plan = 'free'
WHERE plan = 'byok';

-- Note: After this migration:
-- - All former BYOK users are now on 'free' plan with byok_enabled=TRUE
-- - They retain their lifetime session quota (shared between free and BYOK)
-- - New users can enable BYOK on any plan via the toggle-byok endpoint

-- Rollback (if needed):
-- UPDATE users SET plan = 'byok' WHERE byok_enabled = TRUE AND plan = 'free';
-- ALTER TABLE users DROP COLUMN IF EXISTS byok_enabled;
