import os, psycopg

dsn = os.environ.get("DATABASE_URL", "postgresql://tweets_app:tweet@localhost:5432/tweetdb")

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE SCHEMA IF NOT EXISTS raw;
            CREATE UNLOGGED TABLE IF NOT EXISTS raw.stg_copy_probe(
                a INT,
                b TEXT
            );
            TRUNCATE raw.stg_copy_probe;
        """)

        rows = [(1, "foo"), (2, None), (3, "bar\tbaz"), (4, 'quote " here')]

        # ВАЖНО: никакого FORMAT csv/binary — по умолчанию TEXT (tab-delimited, NULL = \N).
        with cur.copy("COPY raw.stg_copy_probe (a, b) FROM STDIN") as cp:
            for r in rows:
                cp.write_row(r)

        cur.execute("SELECT count(*) FROM raw.stg_copy_probe;")
        print("stg_copy_probe rows:", cur.fetchone()[0])
