SET search_path = raw;

-- Планировщику чуть больше свободы/памяти (локально для этого MERGE)
SET LOCAL work_mem = '512MB';
SET LOCAL enable_parallel_hash = on;
SET LOCAL enable_parallel_append = on;

-- =========================
-- 1) USERS: вставляем только новые id
-- =========================
INSERT INTO users (id, screen_name, name, description, verified, protected,
                   followers_count, friends_count, statuses_count, created_at, location, url)
SELECT su.id, su.screen_name, su.name, su.description, su.verified, su.protected,
       su.followers_count, su.friends_count, su.statuses_count, su.created_at, su.location, su.url
FROM stg_users su
LEFT JOIN users u ON u.id = su.id
WHERE su.id IS NOT NULL AND u.id IS NULL
GROUP BY su.id, su.screen_name, su.name, su.description, su.verified, su.protected,
         su.followers_count, su.friends_count, su.statuses_count, su.created_at, su.location, su.url
ON CONFLICT (id) DO NOTHING;

-- Если реально нужны апдейты метрик пользователей (followers_count и т.п.),
-- можно заменить DO NOTHING на DO UPDATE SET ... , но это заметно медленнее.

-- =========================
-- 2) PLACES: только новые id
-- =========================
INSERT INTO places (id, full_name, country, country_code, place_type)
SELECT sp.id, sp.full_name, sp.country, sp.country_code, sp.place_type
FROM stg_places sp
LEFT JOIN places p ON p.id = sp.id
WHERE sp.id IS NOT NULL AND p.id IS NULL
GROUP BY sp.id, sp.full_name, sp.country, sp.country_code, sp.place_type
ON CONFLICT (id) DO NOTHING;

-- =========================
-- 3) HASHTAGS: id стабильный (CRC32) — добавляем новые
-- =========================
INSERT INTO hashtags (id, tag)
SELECT sh.id, sh.tag
FROM stg_hashtags sh
LEFT JOIN hashtags h ON h.id = sh.id
WHERE sh.id IS NOT NULL AND h.id IS NULL
GROUP BY sh.id, sh.tag
ON CONFLICT (id) DO NOTHING;

-- =========================
-- 4) TWEETS: мягкие ссылки допускают NULL, добавляем только новые id
-- =========================
INSERT INTO tweets (id, created_at, full_text, display_from, display_to, lang, user_id, source,
                    in_reply_to_status_id, quoted_status_id, retweeted_status_id, place_id,
                    retweet_count, favorite_count, possibly_sensitive)
SELECT st.id, st.created_at, st.full_text, st.display_from, st.display_to, st.lang, st.user_id, st.source,
       st.in_reply_to_status_id, st.quoted_status_id, st.retweeted_status_id, st.place_id,
       st.retweet_count, st.favorite_count, st.possibly_sensitive
FROM stg_tweets st
LEFT JOIN tweets t ON t.id = st.id
WHERE st.id IS NOT NULL AND t.id IS NULL
GROUP BY st.id, st.created_at, st.full_text, st.display_from, st.display_to, st.lang, st.user_id, st.source,
         st.in_reply_to_status_id, st.quoted_status_id, st.retweeted_status_id, st.place_id,
         st.retweet_count, st.favorite_count, st.possibly_sensitive
ON CONFLICT (id) DO NOTHING;

-- Примечание: если хочется обновлять retweet_count/favorite_count при повторном импорте,
-- можно заменить DO NOTHING на:
-- ON CONFLICT (id) DO UPDATE
--   SET retweet_count = GREATEST(tweets.retweet_count, EXCLUDED.retweet_count),
--       favorite_count = GREATEST(tweets.favorite_count, EXCLUDED.favorite_count);
-- Это медленнее, но даёт «монотонно неубывающие» счётчики.

-- =========================
-- 5) M2M: связи без апдейтов, только дедуп и DO NOTHING
-- =========================

-- tweet_hashtag
INSERT INTO tweet_hashtag (tweet_id, hashtag_id)
SELECT th.tweet_id, th.hashtag_id
FROM stg_tweet_hashtag th
WHERE th.tweet_id IS NOT NULL AND th.hashtag_id IS NOT NULL
GROUP BY th.tweet_id, th.hashtag_id
ON CONFLICT DO NOTHING;

-- tweet_urls (уникальность покрыта индексом по (tweet_id, coalesce(expanded_url,url)))
INSERT INTO tweet_urls (tweet_id, url, expanded_url, display_url, unwound_url)
SELECT tu.tweet_id, tu.url, tu.expanded_url, tu.display_url, tu.unwound_url
FROM stg_tweet_urls tu
WHERE tu.tweet_id IS NOT NULL
GROUP BY tu.tweet_id, tu.url, tu.expanded_url, tu.display_url, tu.unwound_url
ON CONFLICT DO NOTHING;

-- tweet_user_mentions (частичные уникальные индексы по id или по lower(screen_name))
INSERT INTO tweet_user_mentions (tweet_id, mentioned_user_id, mentioned_screen_name, mentioned_name)
SELECT tm.tweet_id, tm.mentioned_user_id, tm.mentioned_screen_name, tm.mentioned_name
FROM stg_tweet_user_mentions tm
WHERE tm.tweet_id IS NOT NULL
GROUP BY tm.tweet_id, tm.mentioned_user_id, tm.mentioned_screen_name, tm.mentioned_name
ON CONFLICT DO NOTHING;

-- tweet_media
INSERT INTO tweet_media (tweet_id, media_id, type, media_url, media_url_https, display_url, expanded_url)
SELECT tm.tweet_id, tm.media_id, tm.type, tm.media_url, tm.media_url_https, tm.display_url, tm.expanded_url
FROM stg_tweet_media tm
WHERE tm.tweet_id IS NOT NULL
GROUP BY tm.tweet_id, tm.media_id, tm.type, tm.media_url, tm.media_url_https, tm.display_url, tm.expanded_url
ON CONFLICT DO NOTHING;
