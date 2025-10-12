-- ============================================================
-- indexes.sql
-- Phase 3: Idempotency (uniqueness) + performance indexes
-- Target schema: raw
-- Run after schema.sql
-- ============================================================

SET search_path TO raw;

-- ------------------------------------------------------------
-- 0) House-keeping: make hashtag uniqueness case-insensitive
--    ER says "functional uniqueness for hashtags by lower(tag)".
--    If schema.sql had a plain UNIQUE(tag), drop it and replace.
-- ------------------------------------------------------------
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


-- Functional unique index enforces case-insensitive uniqueness of tag
CREATE UNIQUE INDEX IF NOT EXISTS idx_hashtags_tag_lower_uk
  ON raw.hashtags (lower(tag));

-- ------------------------------------------------------------
-- 1) Natural primary/unique keys (safety/clarity)
--    (PKs were already defined in schema.sql, we just add helpers if needed)
-- ------------------------------------------------------------
-- Users: natural PK(id) exists; add lookup index by screen_name if you often join by it
CREATE INDEX IF NOT EXISTS idx_users_screen_name
  ON raw.users (lower(screen_name));

-- Places: PK(id) exists; nothing extra required here for now

-- Tweets: PK(id) exists

-- ------------------------------------------------------------
-- 2) Many-to-many de-duplication
--    a) tweet_hashtag is already PRIMARY KEY (tweet_id, hashtag_id) in schema.sql
--    b) Ensure no duplicated URLs per tweet using COALESCE(expanded_url, url)
-- ------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS idx_tweet_urls_unique_per_tweet
  ON raw.tweet_urls (
    tweet_id,
    COALESCE(NULLIF(expanded_url, ''), url)
  );

-- ------------------------------------------------------------
-- 3) Mentions de-duplication
--    Requirement: "mentions uniqueness by mentioned_user_id and/or mentioned_screen_name"
--    Strategy:
--      - If mentioned_user_id is present: enforce uniqueness by (tweet_id, mentioned_user_id)
--      - Else (no id, only screen_name): enforce uniqueness by (tweet_id, lower(mentioned_screen_name))
--    Two partial unique indexes cover the "or" logic without blocking valid rows.
-- ------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS idx_mentions_unique_by_user_id
  ON raw.tweet_user_mentions (tweet_id, mentioned_user_id)
  WHERE mentioned_user_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mentions_unique_by_screen_name
  ON raw.tweet_user_mentions (tweet_id, lower(mentioned_screen_name))
  WHERE mentioned_user_id IS NULL AND mentioned_screen_name IS NOT NULL;

-- ------------------------------------------------------------
-- 4) Join / filter performance indexes
--    Tweets: indexes to support common analytics joins/filters
--    - (user_id, created_at) speeds timelines per user
--    - lang for language filters
--    - *_status_id for reply/quote/retweet graphs
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_tweets_user_created_at
  ON raw.tweets (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tweets_lang
  ON raw.tweets (lang);

CREATE INDEX IF NOT EXISTS idx_tweets_in_reply_to
  ON raw.tweets (in_reply_to_status_id);

CREATE INDEX IF NOT EXISTS idx_tweets_quoted
  ON raw.tweets (quoted_status_id);

CREATE INDEX IF NOT EXISTS idx_tweets_retweeted
  ON raw.tweets (retweeted_status_id);

-- (Optional but useful) lookups by place
CREATE INDEX IF NOT EXISTS idx_tweets_place
  ON raw.tweets (place_id);

-- ------------------------------------------------------------
-- 5) Foreign keys child tables: speed up cascades/joins
--    (FKs are in schema; these indexes help joins from child->parent)
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_tweet_hashtag_tweet
  ON raw.tweet_hashtag (tweet_id);

CREATE INDEX IF NOT EXISTS idx_tweet_hashtag_hashtag
  ON raw.tweet_hashtag (hashtag_id);

CREATE INDEX IF NOT EXISTS idx_tweet_urls_tweet
  ON raw.tweet_urls (tweet_id);

CREATE INDEX IF NOT EXISTS idx_tweet_user_mentions_tweet
  ON raw.tweet_user_mentions (tweet_id);

CREATE INDEX IF NOT EXISTS idx_tweet_media_tweet
  ON raw.tweet_media (tweet_id);

-- ============================================================
-- End of indexes
-- ============================================================
