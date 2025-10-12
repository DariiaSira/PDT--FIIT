SET search_path TO raw;

-- Use UNLOGGED to reduce WAL; drop+recreate or TRUNCATE between runs.
CREATE UNLOGGED TABLE IF NOT EXISTS stg_users (
  id BIGINT,
  screen_name TEXT,
  name TEXT,
  description TEXT,
  verified BOOLEAN,
  protected BOOLEAN,
  followers_count INT,
  friends_count INT,
  statuses_count INT,
  created_at TIMESTAMP,
  location TEXT,
  url TEXT
);

CREATE UNLOGGED TABLE IF NOT EXISTS stg_places (
  id TEXT,
  full_name TEXT,
  country TEXT,
  country_code TEXT,
  place_type TEXT
);

CREATE UNLOGGED TABLE IF NOT EXISTS stg_tweets (
  id BIGINT,
  created_at TIMESTAMP,
  full_text TEXT,
  display_from INT,
  display_to INT,
  lang TEXT,
  user_id BIGINT,
  source TEXT,
  in_reply_to_status_id BIGINT,
  quoted_status_id BIGINT,
  retweeted_status_id BIGINT,
  place_id TEXT,
  retweet_count INT,
  favorite_count INT,
  possibly_sensitive BOOLEAN
);

CREATE UNLOGGED TABLE IF NOT EXISTS stg_hashtags (
  id BIGINT,
  tag TEXT
);

CREATE UNLOGGED TABLE IF NOT EXISTS stg_tweet_hashtag (
  tweet_id BIGINT,
  hashtag_id BIGINT
);

CREATE UNLOGGED TABLE IF NOT EXISTS stg_tweet_urls (
  tweet_id BIGINT,
  url TEXT,
  expanded_url TEXT,
  display_url TEXT,
  unwound_url TEXT
);

CREATE UNLOGGED TABLE IF NOT EXISTS stg_tweet_user_mentions (
  tweet_id BIGINT,
  mentioned_user_id BIGINT,
  mentioned_screen_name TEXT,
  mentioned_name TEXT
);

CREATE UNLOGGED TABLE IF NOT EXISTS stg_tweet_media (
  tweet_id BIGINT,
  media_id BIGINT,
  type TEXT,
  media_url TEXT,
  media_url_https TEXT,
  display_url TEXT,
  expanded_url TEXT
);

