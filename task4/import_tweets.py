import os
import glob
import gzip
import json
import time
from datetime import datetime
from elasticsearch import Elasticsearch, helpers

ES_URL = "http://localhost:9200"
INDEX = "tweets"
DATA_DIR = r"C:\Users\sirad\PycharmProjects\PDT1\tweets_import\data"
es = Elasticsearch(
    [ES_URL],
    request_timeout=60,  
    max_retries=5,
    retry_on_timeout=True,
)

def log(msg: str):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")

def iter_tweets_from_file(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                log(f"  ! JSON decode error in {os.path.basename(path)} line {line_num}")
                continue

            tweet_id = t.get("id") or t.get("id_str")
            if tweet_id is None:
                log(f"  ! Missing id in {os.path.basename(path)} line {line_num}")
                continue

            yield {
                "_index": INDEX,
                "_id": str(tweet_id),
                "_source": t
            }

def import_all_files(data_dir):
    pattern = os.path.join(data_dir, "coronavirus-tweet-id-*.jsonl.gz")
    files = sorted(glob.glob(pattern))
    log(f"Found file: {len(files)}")

    total_ok = 0
    total_failed = 0
    start_all = time.time()

    for path in files:
        log(f"=== Started file: {path} ===")
        start_file = time.time()

        # обёртка над генератором, чтобы считать документы и чанки
        actions = iter_tweets_from_file(path)
        file_ok = 0
        file_failed = 0
        error_examples = []  # примеры ошибок

        # свой цикл по streaming_bulk, чтобы логировать каждый чанк
        for ok, result in helpers.streaming_bulk(
            es,
            actions,
            chunk_size=2000,
            raise_on_error=False,
            raise_on_exception=False,
        ):
            if ok:
                file_ok += 1
            else:
                file_failed += 1
                # сохраним первые несколько ошибок как пример
                error_examples.append(result)
                if file_failed <= 10:
                    log(f"  ! First errors: {json.dumps(result, indent=2)}")

            total = file_ok + file_failed
            if total % 50000  == 0:
                log(f"  Progress: {file_ok} OK, {file_failed} failed")

        elapsed_file = time.time() - start_file
        total_ok += file_ok
        total_failed += file_failed

        log(f"=== Ready file: {os.path.basename(path)} | OK: {file_ok}, Failed: {file_failed}, time: {elapsed_file:.1f}s ===")

        if error_examples:
            log("  Errors examples:")
            for e in error_examples:
                print(json.dumps(e, indent=2))

    elapsed_all = time.time() - start_all
    log(f"DONE. Total OK: {total_ok}, total Failed: {total_failed}, total time: {elapsed_all/60:.1f} min")

if __name__ == "__main__":
    log("Import started")
    import_all_files(DATA_DIR)
    log("Import finished")
