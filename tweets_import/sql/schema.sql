-- ============================================================
-- schema.sql
-- Initial database schema for Twitter import project (DDL v1)
-- Based on ER diagram specification
-- ============================================================

-- Use the "raw" schema for all objects and ensure schema exists on fresh DBs
CREATE SCHEMA IF NOT EXISTS raw;
SET search_path TO raw;


-- ============================================================
-- USERS: Twitter accounts (authors)
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.users (
    id BIGINT PRIMARY KEY,                        -- unique user ID
    screen_name TEXT,                             -- @handle
    name TEXT,                                    -- display name
    description TEXT,                             -- bio text
    verified BOOLEAN,                             -- verified account flag
    protected BOOLEAN,                            -- if the account is private
    followers_count INT,                          -- followers number
    friends_count INT,                            -- following number
    statuses_count INT,                           -- tweets number
    created_at TIMESTAMP,                         -- account creation date
    location TEXT,                                -- profile location
    url TEXT                                      -- profile URL
);


-- ============================================================
-- PLACES: Geo information attached to tweets
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.places (
    id TEXT PRIMARY KEY,                          -- place ID (Twitter format)
    full_name TEXT,                               -- e.g. "Berlin, Germany"
    country TEXT,                                 -- full country name
    country_code TEXT,                            -- ISO country code
    place_type TEXT                               -- e.g. city, country, admin
);

-- ============================================================
-- TWEETS: Core tweet entity
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.tweets (
    id BIGINT PRIMARY KEY,                        -- tweet ID
    created_at TIMESTAMP,                         -- tweet creation time
    full_text TEXT,                               -- tweet text (full mode)
    display_from INT,                             -- display range start
    display_to INT,                               -- display range end
    lang TEXT,                                    -- language code
    user_id BIGINT REFERENCES raw.users(id)
        ON DELETE SET NULL,                       -- author (soft link)
    source TEXT,                                  -- source (web/app/etc.)
    in_reply_to_status_id BIGINT,                 -- reply target tweet id
    quoted_status_id BIGINT,                      -- quoted tweet id
    retweeted_status_id BIGINT,                   -- retweeted tweet id
    place_id TEXT REFERENCES raw.places(id)
        ON DELETE SET NULL,                       -- optional location
    retweet_count INT,                            -- number of retweets
    favorite_count INT,                           -- number of likes
    possibly_sensitive BOOLEAN                    -- sensitive content flag
);

-- Note:
-- reply / quote / retweet IDs are "soft links" without FK constraints,
-- because referenced tweets might not exist in our dataset.

-- ============================================================
-- HASHTAGS: unique hashtag list
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.hashtags (
    id BIGINT PRIMARY KEY,                        -- internal hashtag id
    tag TEXT UNIQUE                               -- actual hashtag text
);

-- ============================================================
-- TWEET_HASHTAG: many-to-many relation between tweets and hashtags
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.tweet_hashtag (
    tweet_id BIGINT REFERENCES raw.tweets(id)
        ON DELETE CASCADE,                        -- if tweet deleted -> remove links
    hashtag_id BIGINT REFERENCES raw.hashtags(id)
        ON DELETE CASCADE,                        -- if hashtag deleted -> remove links
    PRIMARY KEY (tweet_id, hashtag_id)
);

-- ============================================================
-- TWEET_URLS: URLs contained in tweets
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.tweet_urls (
    tweet_id BIGINT REFERENCES raw.tweets(id)
        ON DELETE CASCADE,                        -- belongs to tweet
    url TEXT,
    expanded_url TEXT,
    display_url TEXT,
    unwound_url TEXT
);

-- ============================================================
-- TWEET_USER_MENTIONS: user mentions inside tweets
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.tweet_user_mentions (
  tweet_id BIGINT NOT NULL REFERENCES raw.tweets(id) ON DELETE CASCADE,
  mentioned_user_id BIGINT,           -- soft reference, NO FK on purpose
  mentioned_screen_name TEXT,                   -- @screen_name at time of tweet
    mentioned_name TEXT                           -- display name at time of tweet
);


-- ============================================================
-- TWEET_MEDIA: media objects attached to tweets
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.tweet_media (
    tweet_id BIGINT REFERENCES raw.tweets(id)
        ON DELETE CASCADE,                        -- parent tweet
    media_id BIGINT,                              -- Twitter media id
    type TEXT,                                    -- photo, video, etc.
    media_url TEXT,                               -- http media URL
    media_url_https TEXT,                         -- https version
    display_url TEXT,                             -- shortened display form
    expanded_url TEXT                             -- expanded full URL
);

-- ============================================================
-- End of schema
-- ============================================================

-- asked gpt to add comments and do it beautiful, I think it's too much good :D
