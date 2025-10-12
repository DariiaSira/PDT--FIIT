import os, platform, shutil, time
import psycopg
import psutil

DSN = os.environ.get("DATABASE_URL", "postgresql://tweets_app:tweet@localhost:5432/tweetdb")

def get_system_info(base_dir: str) -> dict:
    cpu = platform.processor() or platform.machine()
    ram_gb = round(psutil.virtual_memory().total / (1024**3), 2) if psutil else None
    disk = shutil.disk_usage(os.path.abspath(os.path.join(base_dir, os.pardir)))
    return {
        "cpu": cpu,
        "ram_gb": ram_gb,
        "disk_total_gb": round(disk.total/(1024**3), 2),
        "disk_used_gb": round(disk.used/(1024**3), 2),
        "disk_free_gb": round(disk.free/(1024**3), 2),
        "python": platform.python_version(),
        "os": f"{platform.system()} {platform.release()}",
    }

def get_db_info(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SHOW server_version;")
        server = cur.fetchone()[0]
        cur.execute("SELECT version();")
        full = cur.fetchone()[0]
    return {"pg_server_version": server, "pg_version_full": full, "psycopg": psycopg.__version__}

def collect_counts_and_orphans(conn) -> tuple[dict, dict]:
    counts = {}
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 'users', count(*) FROM raw.users
            UNION ALL SELECT 'tweets', count(*) FROM raw.tweets
            UNION ALL SELECT 'hashtags', count(*) FROM raw.hashtags
            UNION ALL SELECT 'tweet_urls', count(*) FROM raw.tweet_urls
            UNION ALL SELECT 'tweet_user_mentions', count(*) FROM raw.tweet_user_mentions
            UNION ALL SELECT 'tweet_media', count(*) FROM raw.tweet_media
            UNION ALL SELECT 'tweet_hashtag', count(*) FROM raw.tweet_hashtag
            ORDER BY 1;
        """)
        counts = dict(cur.fetchall())

        cur.execute("""
            SELECT
              sum(CASE WHEN in_reply_to_status_id IS NOT NULL
                        AND NOT EXISTS (SELECT 1 FROM raw.tweets p WHERE p.id = t.in_reply_to_status_id)
                   THEN 1 ELSE 0 END) AS reply_no_parent,
              sum(CASE WHEN quoted_status_id IS NOT NULL
                        AND NOT EXISTS (SELECT 1 FROM raw.tweets p WHERE p.id = t.quoted_status_id)
                   THEN 1 ELSE 0 END) AS quote_no_parent,
              sum(CASE WHEN retweeted_status_id IS NOT NULL
                        AND NOT EXISTS (SELECT 1 FROM raw.tweets p WHERE p.id = t.retweeted_status_id)
                   THEN 1 ELSE 0 END) AS retweet_no_parent
            FROM raw.tweets t;
        """)
        row = cur.fetchone()
        orphans = {
            "reply_no_parent": row[0],
            "quote_no_parent": row[1],
            "retweet_no_parent": row[2],
        }
    return counts, orphans

def main():
    base_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    sysinfo = get_system_info(base_dir)

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("SET search_path = raw, public;")
        dbinfo = get_db_info(conn)
        counts, orphans = collect_counts_and_orphans(conn)

    print("\n==================== PROTOCOL SNAPSHOT ====================")
    print("-- System --")
    print(f"OS: {sysinfo['os']}")
    print(f"CPU: {sysinfo['cpu']}   RAM: {sysinfo['ram_gb']} GB")
    print(f"Disk total/used/free (GB): {sysinfo['disk_total_gb']}/{sysinfo['disk_used_gb']}/{sysinfo['disk_free_gb']}")
    print(f"Python: {sysinfo['python']}")
    print("\n-- Database --")
    print(f"PostgreSQL: {dbinfo['pg_server_version']}   psycopg: {dbinfo['psycopg']}")
    print("\n-- Table counts --")
    for k in sorted(counts.keys()):
        print(f"{k:>20}: {counts[k]:,}")
    print("\n-- Orphan links --")
    for k,v in orphans.items():
        print(f"{k:>20}: {v:,}")
    print("===========================================================\n")

if __name__ == "__main__":
    main()
