import os, glob, gzip, io, time
import orjson as json
import psycopg
from dotenv import load_dotenv
load_dotenv()
from extract import extract_rows

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
BATCH_SIZE = 50000


def run_sql_file(conn, path, label=None, in_tx=True):
    """Запустить SQL-файл. Если in_tx=True — исполняем весь файл одной транзакцией.
    Для файлов с CREATE INDEX CONCURRENTLY используй in_tx=False (по одному стейтменту)."""
    import time, os
    t0 = time.perf_counter()
    sql_path = os.path.abspath(path)
    if not os.path.exists(sql_path):
        raise FileNotFoundError(f"SQL file not found: {sql_path}")

    with conn.cursor() as cur:
        if in_tx:
            cur.execute(open(sql_path, encoding="utf-8").read())
        else:
            buf = []
            for line in open(sql_path, encoding="utf-8"):
                buf.append(line)
                if ";" in line:  # очень простой сплиттер; для наших файлов достаточно
                    stmt = "".join(buf).strip()
                    if stmt:
                        cur.execute(stmt)
                    buf = []
            # хвост без ';'
            tail = "".join(buf).strip()
            if tail:
                cur.execute(tail)

    dt = time.perf_counter() - t0
    print(f"[indexes] {(label or os.path.basename(sql_path))} applied in {dt:.1f}s")

# какие колонки текстовые (по индексу) — чтобы не трогать числа
_TEXT_COLS = {
    "stg_users": {1,2,3,10,11},                # screen_name,name,description,location,url
    "stg_places": {0,1,2,3,4},                 # все text
    "stg_tweets": {2,5,7},                     # full_text,lang,source
    "stg_hashtags": {1},                       # tag
    "stg_tweet_hashtag": set(),                # нет текста
    "stg_tweet_urls": {1,2,3,4},               # url-поля
    "stg_tweet_user_mentions": {2,3},          # screen_name,name
    "stg_tweet_media": {2,3,4,5,6},            # type, media_url*, display/expanded_url
}

def _sanitize_for_table(table: str, row: tuple):
    if not _TEXT_COLS.get(table):
        return row
    tc = _TEXT_COLS[table]
    # создаём список только если реально что-то чистим
    out = list(row)
    changed = False
    for i in tc:
        v = out[i]
        if isinstance(v, str) and "\x00" in v:
            out[i] = v.replace("\x00", "")
            changed = True
    return tuple(out) if changed else row

def sanitize_text(s):
    if s is None:
        return None
    if isinstance(s, str):
        # удаляем только NUL, остальное оставляем (эмодзи/юникод ок)
        if "\x00" in s:
            s = s.replace("\x00", "")
    return s

def sanitize_row(row):
    # прогоняем все текстовые поля через sanitize_text
    return tuple(sanitize_text(v) if isinstance(v, str) else v for v in row)

# buffer writers per table
_buffers = {}
def yield_row(table, row):
    # _buffers.setdefault(table, []).append(_sanitize_for_table(table, row))
    _buffers.setdefault(table, []).append(sanitize_row(row))

def flush_copy(conn, filename=None, batch_no=None):
    tables = {
        "stg_users": [
            "id","screen_name","name","description","verified","protected",
            "followers_count","friends_count","statuses_count","created_at","location","url"
        ],
        "stg_places": ["id","full_name","country","country_code","place_type"],
        "stg_tweets": [
            "id","created_at","full_text","display_from","display_to","lang","user_id","source",
            "in_reply_to_status_id","quoted_status_id","retweeted_status_id","place_id",
            "retweet_count","favorite_count","possibly_sensitive"
        ],
        "stg_hashtags": ["id","tag"],
        "stg_tweet_hashtag": ["tweet_id","hashtag_id"],
        "stg_tweet_urls": ["tweet_id","url","expanded_url","display_url","unwound_url"],
        "stg_tweet_user_mentions": ["tweet_id","mentioned_user_id","mentioned_screen_name","mentioned_name"],
        "stg_tweet_media": ["tweet_id","media_id","type","media_url","media_url_https","display_url","expanded_url"],
    }

    total = 0
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SET LOCAL synchronous_commit = OFF;")
            for tbl, cols in tables.items():
                buf = _buffers.get(tbl) or []
                if not buf:
                    continue
                sql = f"COPY raw.{tbl} ({', '.join(cols)}) FROM STDIN"
                with cur.copy(sql) as cp:
                    for row in buf:
                        cp.write_row(row)
                        total += 1
                _buffers[tbl] = []

    if total:
        info = f"  COPY staged rows: {total}"
        if filename:
            info += f"  |  file: {os.path.basename(filename)}"
        if batch_no is not None:
            info += f"  |  batch #{batch_no}"
        print(info)
    return total

def ingest_file(path, conn):
    with conn.cursor() as cur:
        cur.execute("""
            TRUNCATE raw.stg_users,
                     raw.stg_places,
                     raw.stg_tweets,
                     raw.stg_hashtags,
                     raw.stg_tweet_hashtag,
                     raw.stg_tweet_urls,
                     raw.stg_tweet_user_mentions,
                     raw.stg_tweet_media;
        """)

    count = 0
    batch_no = 0

    with gzip.open(path, "rb") as gz:
        bf = io.TextIOWrapper(io.BufferedReader(gz, buffer_size=4 * 1024 * 1024),
                              encoding="utf-8", errors="ignore")
        for line in bf:
            if not line.strip():
                continue
            obj = json.loads(line)

            # EXTRACT (теперь через extract_rows)
            rows = extract_rows(obj)
            for tbl, batch in rows.items():
                for r in batch:
                    yield_row(tbl, r)

            count += 1
            if count % BATCH_SIZE == 0:
                batch_no += 1
                flush_copy(conn, filename=path, batch_no=batch_no)


    # # tail
    # batch_no += 1
    # flush_copy(conn, filename=path, batch_no=batch_no)
    #
    # # MERGE once per file
    # merge_sql_path = os.path.join(os.path.dirname(__file__), '..', 'sql', 'merge.sql')
    # with conn.cursor() as cur:
    #     cur.execute("SET LOCAL synchronous_commit = OFF;")
    #     with open(merge_sql_path, encoding="utf-8") as f:
    #         cur.execute(f.read())

    # tail
    batch_no += 1
    flush_copy(conn, filename=path, batch_no=batch_no)

    merge_sql_path = os.path.join(os.path.dirname(__file__), '..', 'sql', 'merge.sql')
    with conn.cursor() as cur:
        # >>> ускоряем MERGE этой сессии
        cur.execute("""
            SET LOCAL synchronous_commit = OFF;
            SET LOCAL work_mem = '512MB';
            SET LOCAL maintenance_work_mem = '2GB';
            SET LOCAL enable_parallel_hash = on;
            SET LOCAL enable_parallel_append = on;
            ANALYZE raw.stg_users;
            ANALYZE raw.stg_places;
            ANALYZE raw.stg_tweets;
            ANALYZE raw.stg_hashtags;
            ANALYZE raw.stg_tweet_hashtag;
            ANALYZE raw.stg_tweet_urls;
            ANALYZE raw.stg_tweet_user_mentions;
            ANALYZE raw.stg_tweet_media;
        """)
        with open(merge_sql_path, encoding="utf-8") as f:
            cur.execute(f.read())

    return count


def process_one_file(path, dsn):
    t0 = time.perf_counter()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SET search_path = raw, public;
                SET jit=off; SET work_mem='256MB'; SET maintenance_work_mem='1GB';
                SET temp_buffers='64MB'; SET synchronous_commit=off;
            """)
        n = ingest_file(path, conn)
    dt = time.perf_counter() - t0
    rps = (n / dt) if dt > 0 else 0
    print(f"Done: file={os.path.basename(path)}  rows={n:,}  time={dt:.1f}s  rps={rps:,.0f}")
    return n, dt

def main():
    dsn = os.environ.get("DATABASE_URL", "postgresql://tweets_app:tweet@localhost:5432/tweetdb")
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.jsonl.gz")))

    start_ts = time.time()

    # 1) Подключаемся и применяем "идемпотентные" индексы (безопасно: IF NOT EXISTS)
    indexes_idem = os.path.join(os.path.dirname(__file__), '..', 'sql', 'indexes_idempotent.sql')
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET search_path = raw, public;")
        run_sql_file(conn, indexes_idem, label="indexes_idempotent.sql", in_tx=True)

    total_rows = 0
    total_time = 0.0

    from concurrent.futures import ProcessPoolExecutor, as_completed
    # оставляем 1 процесс (общий staging). Параллель включим позже (TEMP staging).
    with ProcessPoolExecutor(max_workers=1) as ex:
        futs = [ex.submit(process_one_file, p, dsn) for p in files]
        for f in as_completed(futs):
            n, dt = f.result()
            total_rows += n
            total_time += dt

    # после загрузки — производственные индексы
    indexes_perf = os.path.join(os.path.dirname(__file__), '..', 'sql', 'indexes_perf.sql')
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET search_path = raw, public;")
        run_sql_file(conn, indexes_perf, label="indexes_perf.sql", in_tx=True)

    # финальный отчёт: системная/DB инфа + counts + orphan-метрики
    print(f"[perf-total] files={len(files)}  rows={total_rows:,}  time={total_time:.1f}s  rps={(total_rows/total_time) if total_time>0 else 0:,.0f}")



if __name__ == "__main__":
    main()
