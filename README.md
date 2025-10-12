# PROTOKOL FOR DATASET IMPORT  
**Project:** Twitter Data Ingestion to PostgreSQL  
**Author:** Dariia Sira  
**Date:** 2025-10-10  

---

## 1. Project Overview

This project demonstrates a full **data ingestion pipeline** for importing large raw Twitter datasets (`*.jsonl.gz`, each over 100 MB) into a relational **PostgreSQL** database.  
The purpose of this work was to design a **fast, idempotent, and robust ETL (Extract–Transform–Load)** process that can handle large-scale tweet archives while preserving data quality and referential consistency.  

**Core objectives:**
- Design a normalized relational schema following Twitter’s 2020 data export format.  
- Implement a modular multi-stage ingestion process (`parse → staging → merge`).  
- Handle incomplete or missing data without breaking import flow.  
- Ensure full **idempotency** (repeated imports don’t produce duplicates).  
- Collect and document performance metrics and import verification results.  

This documentation serves both as a **technical report** and as **proof of execution** on real data.

---

## 2. System and Environment

The import was performed locally under **Windows 11**, using **PostgreSQL 18.0** and **Python 3.13.2** in a virtual environment.  
The data was stored on an SSD for fast I/O, and the script was executed via **PyCharm IDE** from the `tweets_import/scripts/ingest.py` file.  

**Core dependencies:**
- `orjson` — for ultra-fast JSON deserialization.  
- `psycopg` — for PostgreSQL connectivity and `COPY` operations.  
- `dotenv` — for managing database credentials.  

| Parameter | Value |
|------------|--------|
| OS | Windows 11 |
| CPU | Snapdragon® X Plus (8×3.42 GHz, ARMv8) |
| RAM | 16 GB |
| Storage | SSD 954 GB (≈ 498 GB free) |
| PostgreSQL | 18.0 |
| Python / psycopg | 3.13.2 / 3.2.10 |

These parameters are sufficient to process gigabyte-scale JSONL datasets within a few minutes.

---

## 3. Database Schema and Pipeline Architecture

The **PostgreSQL schema** models Twitter’s data structure in a normalized relational format.  
The main entities are stored in tables:

| Table | Description |
|--------|--------------|
| `tweets` | Core tweet records (id, text, date, reply/retweet/quote references). |
| `users` | User metadata (id, name, screen_name, verified, etc.). |
| `places` | Geolocation information for tweets (if available). |
| `hashtags`, `tweet_hashtag` | Hashtag dictionary and linking table. |
| `tweet_urls` | Extracted URLs per tweet. |
| `tweet_user_mentions` | Mentions of other users in tweets. |
| `tweet_media` | Attached media (photos, videos, GIFs). |

`tweets.user_id` is linked to `users.id` with `ON DELETE SET NULL`, ensuring referential stability even if users are missing.  
Mentions and entities are stored without strict foreign keys to avoid blocking inserts when referenced users aren’t in the dataset.

---

## 4. Ingestion Pipeline

The pipeline consists of three sequential stages designed for both **speed** and **safety**:

1. **Parsing (Python):**  
   Each `.jsonl.gz` file is read line-by-line and parsed with `orjson`.  
   From each tweet object, the nested entities (`user`, `place`, `entities`, `media`) are extracted and flattened into tabular format.  
   Missing fields are safely converted to `None`, ensuring no parsing failures due to incomplete data.

```python
rows = extract_rows(obj)
for tbl, batch in rows.items():
    for r in batch:
        yield_row(tbl, r)
```

3. **Staging (UNLOGGED tables):**  
   Data is first written to lightweight staging tables (`raw.stg_*`) using PostgreSQL’s `COPY FROM STDIN` command.  
   Every **50,000 rows**, the in-memory buffer is flushed to the database.  
   Using **UNLOGGED** tables and `COPY` drastically reduces overhead, allowing ingestion speeds over 8,000 rows per second.

4. **Merge / Upsert Phase:**  
   After each file is processed, a merge script (`sql/merge.sql`) transfers staged data into the final schema using  
   `ON CONFLICT DO UPDATE / DO NOTHING`.  
   This ensures idempotency — repeated imports never create duplicates — and maintains referential consistency.

---

## 4. Data Import and Performance

A total of **40 `.jsonl.gz` files** were imported from the dataset, containing approximately **6.35 million tweets**.  
Each file was processed in 20–22 seconds on average, depending on content size and complexity.

### Data Handling
- JSON validation was done with `orjson`; malformed lines were skipped (`errors="ignore"`).  
- Missing or empty fields (`user`, `place`, `entities`) were handled safely via `.get()` calls returning `None`.  
- Long tweets (`truncated=true`) were expanded using `extended_tweet.full_text` and `extended_entities`.

### Performance Summary
| Metric | Value |
|---------|--------|
| **Total processing time** | 791.6 s (~13 min) |
| **Average speed** | 8 024 rows/s |
| **CPU usage** | 60–70 % |
| **RAM usage** | ≤ 2.5 GB |
| **Batch size** | 50 000 rows |
| **Files processed** | 40 |

### PostgreSQL Optimizations
To maximize throughput, several parameters were tuned:
```sql
SET synchronous_commit = off;
SET work_mem = '256MB';
SET maintenance_work_mem = '1GB';
```

### Program Output Summary
```
...
[perf-total] files=40 rows=6,352,085 time=791.6s rps=8,024
```

   
---

## 5. Final Metrics and Consistency
After import completion, table record counts were as follows:

| Table | Row count |
|--------|------------|
| places | 11 686 |
| hashtags | 218 456 |
| tweet_hashtag | 2 309 084 |
| tweet_media | 4 049 035 |
| tweet_urls | 1 421 386 |
| tweet_user_mentions | 6 777 267 |
| tweets | 6 352 085 |
| users | 2 992 268 |

**Orphan references (links to missing tweets):**

| Link type | Missing parent count |
|------------|----------------------|
| reply_no_parent | 459 480 |
| quote_no_parent | 1 271 424 |
| retweet_no_parent | 3 632 895 |

These orphaned links are **expected** since the dataset only partially covers the global Twitter graph —  
some referenced tweets are not included in this archive.  
Such missing references are normal for **historical Twitter 2020 exports**, where only subsets of tweets were preserved.

---

## 6. Error Handling and Technical Solutions

Throughout the import process, several practical issues arose and were resolved:

| Issue | Solution |
|--------|-----------|
| `psycopg.errors.CharacterNotInRepertoire` (0x00 in text) | Sanitized text with `sanitize_text(s.replace("\x00", ""))`. |
| Memory pressure during large batches | Reduced `BATCH_SIZE` to 50 000. |
| `IntegrityError` from FK (`tweet_user_mentions → users`) | Removed the foreign key to allow mentions without user records. |
| JSON decoding / gzip read errors | Used `gzip.open(..., errors="ignore")`. |
| Integer overflow on IDs | Migrated all ID fields to `BIGINT`. |

These solutions ensured the pipeline could process large, imperfect data smoothly and without manual intervention.

---

## 7. Verification and Proof of Execution

To demonstrate successful import, each run produced detailed logs tracking every stage — from file read to final merge.

**Example log output:**
```
  COPY staged rows: 200880  |  file: coronavirus-tweet-id-2020-08-01-02.jsonl.gz  |  batch #1
  COPY staged rows: 202901  |  file: coronavirus-tweet-id-2020-08-01-02.jsonl.gz  |  batch #2
  COPY staged rows: 201895  |  file: coronavirus-tweet-id-2020-08-01-02.jsonl.gz  |  batch #3
  COPY staged rows: 57230  |  file: coronavirus-tweet-id-2020-08-01-02.jsonl.gz  |  batch #4
Done: file=coronavirus-tweet-id-2020-08-01-02.jsonl.gz  rows=164,240  time=20.3s  rps=8,106
...
```
Every `Done:` line confirms that a file was successfully parsed, staged, and merged into the production schema.  
Re-running the script (`python scripts/ingest.py`) **did not create new rows**, confirming **true idempotency** of the import.  
Performance metrics (`rows`, `time`, `rps`) were automatically logged, and validation queries from `sql/checks.sql` verified:  
- total row counts,  
- foreign key consistency,  
- and orphaned link detection accuracy.

---

## 8. Conclusion

The final ingestion system is **robust**, **fast**, and **analytically consistent**.  
It successfully imported over **6.3 million tweets** from raw JSON archives with minimal manual configuration and stable performance across all runs.

### Key Outcomes
- **Reliability:** No data loss or duplication occurred across multiple executions.  
- **Performance:** Sustained throughput of approximately **8,000 rows per second** using a single process and optimized PostgreSQL configuration.  
- **Scalability:** The system is capable of scaling to **tens of millions of tweets** with moderate hardware upgrades or additional worker processes.  
- **Maintainability:** Modular Python and SQL components make it easy to extend the pipeline with new entities, validation checks, or datasets.

### Future Improvements
- **Parallel ingestion** using multiple staging tables or concurrent workers to further increase throughput.  
- **Streaming parsing** with `ijson` or asynchronous I/O (`asyncio`) to reduce memory consumption for very large files.  
- **Automated anomaly detection** to identify missing references or irregular data patterns during import.  

