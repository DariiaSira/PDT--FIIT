-- ============================================================
-- indexes_perf.sql
-- Performance indexes (create AFTER bulk load)
-- Target schema: raw
-- NOTE: If you need near-zero blocking on a live DB,
--       switch to CREATE INDEX CONCURRENTLY (one per statement).
-- ============================================================

SET search_path TO raw;

-- Tweets: common filters/joins
CREATE INDEX IF NOT EXISTS idx_tweets_user_created_at  ON tweets (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tweets_lang             ON tweets (lang);
CREATE INDEX IF NOT EXISTS idx_tweets_in_reply_to      ON tweets (in_reply_to_status_id);
CREATE INDEX IF NOT EXISTS idx_tweets_quoted           ON tweets (quoted_status_id);
CREATE INDEX IF NOT EXISTS idx_tweets_retweeted        ON tweets (retweeted_status_id);
CREATE INDEX IF NOT EXISTS idx_tweets_place            ON tweets (place_id);

-- Children -> parent join helpers
CREATE INDEX IF NOT EXISTS idx_tweet_hashtag_tweet     ON tweet_hashtag (tweet_id);
CREATE INDEX IF NOT EXISTS idx_tweet_hashtag_hashtag   ON tweet_hashtag (hashtag_id);
CREATE INDEX IF NOT EXISTS idx_tweet_urls_tweet        ON tweet_urls (tweet_id);
CREATE INDEX IF NOT EXISTS idx_tweet_user_mentions_twt ON tweet_user_mentions (tweet_id);
CREATE INDEX IF NOT EXISTS idx_tweet_media_tweet       ON tweet_media (tweet_id);

-- Users lookups by handle
CREATE INDEX IF NOT EXISTS idx_users_screen_name       ON users (lower(screen_name));

-- ============================================================
-- End of indexes_perf.sql
-- ============================================================
