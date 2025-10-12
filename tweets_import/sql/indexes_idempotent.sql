-- ============================================================
-- indexes_idempotent.sql
-- Uniqueness / idempotency indexes (keep during ingest)
-- Target schema: raw
-- ============================================================

SET search_path TO raw;

-- 0) Hashtags: enforce case-insensitive uniqueness by lower(tag)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema = 'raw'
      AND table_name   = 'hashtags'
      AND constraint_type = 'UNIQUE'
      AND constraint_name = 'hashtags_tag_key'
  ) THEN
    EXECUTE 'ALTER TABLE raw.hashtags DROP CONSTRAINT hashtags_tag_key';
  END IF;
EXCEPTION
  WHEN undefined_table THEN NULL;
  WHEN undefined_object THEN NULL;
END
$$ LANGUAGE plpgsql;

CREATE UNIQUE INDEX IF NOT EXISTS idx_hashtags_tag_lower_uk
  ON hashtags (lower(tag));

-- 1) tweet_urls: one URL per tweet (coalesce expanded_url/url)
CREATE UNIQUE INDEX IF NOT EXISTS idx_tweet_urls_unique_per_tweet
  ON tweet_urls (tweet_id, COALESCE(NULLIF(expanded_url, ''), url));

-- 2) tweet_user_mentions: uniqueness by user_id OR (lower(screen_name)) when id is missing
CREATE UNIQUE INDEX IF NOT EXISTS idx_mentions_unique_by_user_id
  ON tweet_user_mentions (tweet_id, mentioned_user_id)
  WHERE mentioned_user_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mentions_unique_by_screen_name
  ON tweet_user_mentions (tweet_id, lower(mentioned_screen_name))
  WHERE mentioned_user_id IS NULL AND mentioned_screen_name IS NOT NULL;

-- 3) tweet_hashtag: de-dup (if not already PK in schema)
CREATE UNIQUE INDEX IF NOT EXISTS idx_tweet_hashtag_uk
  ON tweet_hashtag (tweet_id, hashtag_id);

-- ============================================================
-- End of indexes_idempotent.sql
-- ============================================================
