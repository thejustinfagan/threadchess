-- =============================================================================
-- Battle Dinghy - Add last_checked_tweet_id Column
-- =============================================================================
-- This migration adds a column to track the last processed tweet per game thread.
-- This enables monitoring game threads for fire commands WITHOUT requiring @mentions.
--
-- Safe to run multiple times (idempotent)
-- =============================================================================

-- Add last_checked_tweet_id column to games table
-- This tracks the most recent tweet we've processed for each game thread
-- Using TEXT instead of BIGINT because Twitter IDs can exceed JavaScript safe integer
ALTER TABLE public.games
ADD COLUMN IF NOT EXISTS last_checked_tweet_id TEXT;

-- Add comment explaining the column
COMMENT ON COLUMN public.games.last_checked_tweet_id IS
'Tracks the last tweet ID processed in this game thread. Used to avoid reprocessing tweets when monitoring for fire commands.';

-- =============================================================================
-- VERIFICATION
-- =============================================================================
-- Run this query after executing the script to verify the column was added:
--
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'games' AND column_name = 'last_checked_tweet_id';
--
-- Expected output: last_checked_tweet_id | text
-- =============================================================================
