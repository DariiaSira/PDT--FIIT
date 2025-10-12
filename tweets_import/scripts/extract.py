# scripts/extract.py
# Pure extraction of one tweet JSON -> rows for staging tables (no DB here)

from datetime import datetime
import re
import zlib

# --- helpers (local) ---------------------------------------------------------

_A_TAG_RE = re.compile(r"<.*?>(.*?)<.*?>")

def _clean_source(src: str | None) -> str | None:
    if not src:
        return None
    m = _A_TAG_RE.match(src)
    return m.group(1) if m else src

def _ts(s: str | None):
    if not s:
        return None
    # Twitter legacy example: "Sat Aug 01 01:59:54 +0000 2020"
    try:
        return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y").replace(tzinfo=None)
    except Exception:
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None

def _to_int(v):
    try:
        return int(v) if v is not None else None
    except Exception:
        return None

def _rng(obj: dict, key: str):
    arr = obj.get(key)
    if isinstance(arr, (list, tuple)) and len(arr) >= 2:
        a, b = arr[0], arr[1]
        return (_to_int(a) if a is not None else None,
                _to_int(b) if b is not None else None)
    return (None, None)

def _stable_hashtag_id(tag: str) -> int:
    # deterministic 32-bit (fits into INT; our schema uses BIGINT so it's fine)
    return zlib.crc32(tag.lower().encode("utf-8"))

# --- main API ----------------------------------------------------------------

def extract_rows(t: dict) -> dict[str, list[tuple]]:
    """
    Convert one tweet JSON object into rows for staging tables.
    Returns dict: table_name -> list of tuples (rows).
    """
    u = (t.get("user") or {})
    p = (t.get("place") or {})

    # Long tweets (truncated) -> use extended_tweet
    et = t.get("extended_tweet") or {}
    use_ext = bool(t.get("truncated") and (et.get("full_text") or et.get("entities")))
    full_text = (et.get("full_text") if use_ext else (t.get("full_text") or t.get("text")))
    ents = (et.get("entities") if use_ext else (t.get("entities") or {}))

    # display_text_range may be under extended_tweet
    dfrom, dto = _rng(et if use_ext else t, "display_text_range")

    # refs
    retweet_id = _to_int((t.get("retweeted_status") or {}).get("id"))
    quote_id   = _to_int(t.get("quoted_status_id"))
    reply_id   = _to_int(t.get("in_reply_to_status_id"))

    rows = {
        "stg_tweets": [],
        "stg_users": [],
        "stg_places": [],
        "stg_hashtags": [],
        "stg_tweet_hashtag": [],
        "stg_tweet_urls": [],
        "stg_tweet_user_mentions": [],
        "stg_tweet_media": [],
    }

    tweet_id = _to_int(t.get("id"))
    if tweet_id is None:
        return rows  # skip

    # tweets
    rows["stg_tweets"].append((
        tweet_id,
        _ts(t.get("created_at")),
        full_text,
        dfrom, dto,
        t.get("lang"),
        _to_int(u.get("id")),
        _clean_source(t.get("source")),
        reply_id,
        quote_id,
        retweet_id,
        p.get("id"),
        _to_int(t.get("retweet_count")),
        _to_int(t.get("favorite_count")),
        t.get("possibly_sensitive"),
    ))

    # users (author)
    uid = _to_int(u.get("id"))
    if uid is not None:
        rows["stg_users"].append((
            uid,
            u.get("screen_name"),
            u.get("name"),
            u.get("description"),
            u.get("verified"),
            u.get("protected"),
            _to_int(u.get("followers_count")),
            _to_int(u.get("friends_count")),
            _to_int(u.get("statuses_count")),
            _ts(u.get("created_at")),
            u.get("location"),
            (u.get("url") or (u.get("entities", {}).get("url", {}).get("urls", [{}])[0].get("expanded_url")))
        ))

    # place
    if p.get("id"):
        rows["stg_places"].append((
            p.get("id"),
            p.get("full_name"),
            p.get("country"),
            p.get("country_code"),
            p.get("place_type"),
        ))

    # hashtags
    for h in (ents.get("hashtags") or []):
        tag = h.get("text")
        if tag:
            hid = _stable_hashtag_id(tag)
            rows["stg_hashtags"].append((hid, tag))
            rows["stg_tweet_hashtag"].append((tweet_id, hid))

    # urls
    for uo in (ents.get("urls") or []):
        rows["stg_tweet_urls"].append((
            tweet_id,
            uo.get("url"),
            uo.get("expanded_url"),
            uo.get("display_url"),
            (uo.get("unwound_url") or uo.get("expanded_url"))
        ))

    # mentions
    for m in (ents.get("user_mentions") or []):
        rows["stg_tweet_user_mentions"].append((
            tweet_id,
            _to_int(m.get("id")),
            m.get("screen_name"),
            m.get("name"),
        ))

    # media (prefer extended_entities)
    media_src = ((t.get("extended_entities") or {}).get("media")) or (ents.get("media") or [])
    for mo in media_src:
        rows["stg_tweet_media"].append((
            tweet_id,
            _to_int(mo.get("id")),
            mo.get("type"),
            mo.get("media_url"),
            mo.get("media_url_https"),
            mo.get("display_url"),
            mo.get("expanded_url"),
        ))

    return rows
