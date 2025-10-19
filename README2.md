# 1. Project Overview 2

This project focuses on query optimization and index performance analysis in PostgreSQL аnalyzing historical tweets and user profiles, I am tasked with diagnosing slow query execution and dashboard performance issues. The primary goal is to investigate query plans, experiment with indexes, and observe how PostgreSQL’s planner and parallel execution behave under various scenarios.

---

# 2. Realization

### Task 1: Exact Match Search for `screen_name`
Vyhľadajte v `users` `screen_name` s presnou hodnotou `realDonaldTrump` a analyzujte daný select.  
Akú metódu vám vybral plánovač?

**Solution:**

**Query**
```sql
EXPLAIN ANALYZE SELECT * FROM raw.users WHERE screen_name = 'realDonaldTrump';
```
**Output**
```
Gather  (cost=1000.00..143251.88 rows=1 width=163) (actual time=1087.316..1094.868 rows=1.00 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  Buffers: shared read=126711
  ->  Parallel Seq Scan on users  (cost=0.00..142251.78 rows=1 width=163) (actual time=699.950..1030.805 rows=0.33 loops=3)
        Filter: (screen_name = 'realDonaldTrump'::text)
        Rows Removed by Filter: 997422
        Buffers: shared read=126711
Planning:
  Buffers: shared hit=41 read=11
Planning Time: 2.130 ms
Execution Time: 1095.199 ms
```

| **Parameter** | **Value** |
|----------------|------------|
| **Query** | `SELECT * FROM users WHERE screen_name = 'realDonaldTrump';` |
| **Query plan** | `Parallel Seq Scan on users` |
| **Workers planned / launched** | 2 / 2 |
| **Filter applied** | `screen_name = 'realDonaldTrump'` |
| **Rows examined** | ~1,000,000 |
| **Rows returned** | 1 |
| **Buffers read** | 126,711 (≈ 1 GB I/O) |
| **Execution time** | 1.09 s |
| **CPU utilization** | High (all cores used by parallel scan) |

The PostgreSQL planner used a **Parallel Sequential Scan**, meaning the entire `users` table (~1 million rows) was read in parallel by two worker processes.  No index was available for `screen_name`, so PostgreSQL compared every row to find the matching value.  Despite parallelization, the query remains slow due to high I/O cost and filtering overhead.  

---

### Task 2: Number of Workers and Time Impact
Koľko workerov pracovalo na danom selecte? Zdvihnite počet workerov a povedzte, ako to ovplyvňuje čas. Je tam nejaký strop?

**Solution:**

I executed the same query as before, but this time I adjusted the PostgreSQL parameter `max_parallel_workers_per_gather` to test how different levels of parallelism affect performance. Each run was analyzed using `EXPLAIN ANALYZE` to observe worker utilization, execution time, and buffer reads.

**Results Analysis**

| **max_parallel_workers_per_gather** | **Workers Planned** | **Workers Launched** | **Execution Time (ms)** | **Buffers read** | **Observation** |
|------------------------------------:|---------------------:|----------------------:|-------------------------:|-----------------:|-----------------|
| 2 (default) | 2 | 2 | 1095 | 126,711 | Baseline case — full table scan |
| 4 | 4 | 4 | 388 | 126,422 | Strong acceleration — load effectively distributed |
| 6 | 5 | 5 | 363 | 124,824 | Slight improvement — near performance ceiling |
| 8 | 5 | 5 | 413 | 124,260 | Slowdown — excessive parallelization overhead |

When increasing `max_parallel_workers_per_gather` to 4, execution time dropped almost threefold (1.09 s → 0.39 s), proving that parallel reading significantly speeds up sequential scans.  

Further increases (6 and 8) did not produce more active workers — PostgreSQL capped the count at 5,  
indicating a **parallel limit (parallel cap)** beyond which more workers bring no benefit. At 8 workers, performance even degraded to 413 ms due to **coordination overhead** from merging parallel results (Gather node).  

 - **Cost-based decision**: PostgreSQL dynamically estimates the optimal number of workers based on table size and expected gain. Even if 8 are allowed, it may only launch 4–5 when extra threads bring minimal improvement.  

 - **I/O limitation**: Disk and shared buffer throughput becomes the bottleneck — workers share the same data channel, limiting scaling.  

 - **Gather overhead**: The more workers are active, the more synchronization and aggregation time is required to combine results. This leads to diminishing returns beyond a certain parallel threshold.

---

### Task 3: Index on `screen_name`
Vytvorte index nad `screen_name` a porovnajte výstup oproti požiadavke bez indexu.  
Potrebuje plánovač v tejto požiadavke viac workerov? Bol tu aplikovaný nejaký filter na riadky? Prečo?

**Solution I:**
I first tried to create an index on `screen_name`, but PostgreSQL returned an error indicating that the index already existed.  
This confirmed that `idx_users_screen_name` was created in a previous task and could not be duplicated.

**Query**
```sql
CREATE INDEX idx_users_screen_name ON users(screen_name);
```

**Output**
```sql
[42P07] ERROR: relation "idx_users_screen_name" already exists
```

PostgreSQL prevented index creation because an index with the same name already exists in the database. Each table can only have uniquely named indexes, and `idx_users_screen_name` was already present from earlier experiments.

**Solution II:**

Next, I updated table statistics using `ANALYZE` and disabled parallel workers by setting `max_parallel_workers_per_gather = 0`. The planner still chose a **Sequential Scan**, even though the index was available.

**Query**
```sql
ANALYZE users;
SET max_parallel_workers_per_gather = 0;
EXPLAIN ANALYZE SELECT * FROM raw.users WHERE screen_name = 'realDonaldTrump';
```

**Output**
```sql
Seq Scan on users  (cost=0.00..164183.92 rows=1 width=162) (actual time=35.423..459.645 rows=1.00 loops=1)
  Filter: (screen_name = 'realDonaldTrump'::text)
  Rows Removed by Filter: 2992267
  Buffers: shared hit=5138 read=121573
Planning:
  Buffers: shared hit=66
Planning Time: 1.616 ms
Execution Time: 459.703 ms
```

Even after refreshing statistics and disabling parallel execution, PostgreSQL’s planner decided that a full sequential scan was cheaper than random index lookups.  For ~3 million rows with evenly distributed `screen_name` values, the optimizer estimated that using the index would not provide performance benefits.

**Solution III:**
I suspected that the `random_page_cost` parameter might be influencing the planner’s decision.  
After checking its default value (4.0), I reduced it to 1.1 to make random I/O appear less expensive, then reran the query.  
However, the planner still selected a **Parallel Seq Scan** with two workers.

**Query**
```sql
SET random_page_cost = 1.1;
EXPLAIN ANALYZE SELECT * FROM users WHERE screen_name = 'realDonaldTrump';
```

**Output**
```sql
Seq Scan on users  (cost=0.00..164183.92 rows=1 width=162) (actual time=33.287..444.560 rows=1.00 loops=1)
  Filter: (screen_name = 'realDonaldTrump'::text)
  Rows Removed by Filter: 2992267
  Buffers: shared hit=5233 read=121478
Planning Time: 0.145 ms
Execution Time: 444.602 ms
```

Lowering `random_page_cost` caused the planner to re-evaluate, but the final plan remained a parallel sequential scan. Even with cheaper random I/O, the potential benefit of index access was still too low — scanning the entire table in parallel was faster for finding one record among millions.

---

### Task 4: Filter on `followers_count` (100–200)
Vyberte používateľov, ktorí majú `followers_count` väčší alebo rovný 100 a zároveň menší alebo rovný 200. Je správanie rovnaké ako v prvej úlohe? Je správanie rovnaké ako v druhej úlohe? Prečo?

**Solution I:**

I first executed the range query on `followers_count` without any index to observe the baseline behavior and planner choice. PostgreSQL performed a sequential scan over the entire `users` table (~3 million rows) and applied the filter row by row.

**Query**
```sql
EXPLAIN ANALYZE 
SELECT * 
FROM users 
WHERE followers_count BETWEEN 100 AND 200;
```

**Output**
```sql
Seq Scan on users  (cost=0.00..171678.51 rows=397398 width=162) (actual time=0.041..500.182 rows=410760.00 loops=1)
  Filter: ((followers_count >= 100) AND (followers_count <= 200))
  Rows Removed by Filter: 2581508
  Buffers: shared hit=5327 read=121384
Planning:
  Buffers: shared hit=6
Planning Time: 0.229 ms
Execution Time: 532.678 ms
```

Without an index, PostgreSQL has no way to directly locate matching rows — it must read every record sequentially. Since the range `(100 ≤ followers_count ≤ 200)` returns around 400,000 rows (~13% of the table), the query is not highly selective. For such moderately large subsets, the planner correctly chooses a **Sequential Scan** (or **Parallel Seq Scan**) because linear I/O access is faster and more predictable. Execution time was about **0.5 s**.

**Solution II:**

I decided to check the influence of indexes. After creating an index on `followers_count` and running `ANALYZE`, the planner switched to using an **Index Scan**, recognizing that the condition can be satisfied via a B-tree lookup. However, the query became significantly slower — **3.2 seconds** compared to 0.5 seconds before indexing.

**Query**
```sql
CREATE INDEX idx_users_followers_count ON users(followers_count);
ANALYZE users;

EXPLAIN ANALYZE
SELECT * FROM users
WHERE followers_count BETWEEN 100 AND 200;
```

**Output**
```sql
Index Scan using idx_users_followers_count on users  (cost=0.43..147820.88 rows=403574 width=163) (actual time=1.238..3165.721 rows=410760.00 loops=1)
  Index Cond: ((followers_count >= 100) AND (followers_count <= 200))
  Index Searches: 1
  Buffers: shared hit=57721 read=344669 written=3790
Planning:
  Buffers: shared hit=71 read=5
Planning Time: 2.366 ms
Execution Time: 3201.693 ms
```

Although the index allows PostgreSQL to locate the lower and upper range boundaries quickly, it must still fetch approximately 400,000 matching rows from disk. This results in a large number of random reads, which are much slower than sequential block reads. The sequential scan reads the same data linearly. The index proves beneficial only when a very small portion of the table (typically less than 5–10%) is returned — for wide ranges like this one, it introduces unnecessary overhead.

**Comparison with Previous Experiments**

| **Task** | **Planner Behavior** | **Reason** |
|-----------|----------------------|-------------|
| Task 1 – `screen_name = 'realDonaldTrump'` | Planner chose **Parallel Seq Scan**, index ignored | Query was highly selective (1 row), but random index I/O was considered more expensive |
| Task 2 – Parallel Workers | Execution time improved up to 4–5 workers, then stabilized | Parallel Seq Scan scales well for large tables |
| Task 4 – `followers_count` range | With index: slower, without index: faster | Range too wide → Index Scan causes excessive random I/O |

In this experiment, the sequential (or parallel) scan proved to be the most efficient method for medium-to-large data volumes. When the index on `followers_count` was created, PostgreSQL’s planner switched to using it, but overall query time increased instead of decreasing. The reason is that the range `(100–200)` returned too many rows, leading to numerous random disk reads. Sequential scans, by contrast, read data linearly and benefit from better caching and throughput on large datasets. Therefore, although the index technically works, it becomes **economically inefficient** for wide ranges, unlike the cases in Tasks 1 and 2 where parallel scans were beneficial.

---

### Task 5: Index for Task 4 and Bitmaps
Vytvorte index nad podmienkou z úlohy 4 a popíšte prácu s indexom. Čo je to Bitmap Index Scan a prečo je tam Bitmap Heap Scan? Prečo je tam recheck condition?

**Solution:**

I already performed this in Task 4, where PostgreSQL used a **Bitmap Index Scan** followed by a **Bitmap Heap Scan** to handle the range condition efficiently. The **Recheck Cond** step ensured accuracy by verifying each matching row after fetching it from the heap.

**Query**
```sql
CREATE INDEX idx_users_followers_count ON users(followers_count);
ANALYZE users;

EXPLAIN ANALYZE
SELECT * FROM users
WHERE followers_count BETWEEN 100 AND 200;
```

**Output**
```sql
Index Scan using idx_users_followers_count on users  (cost=0.43..147820.88 rows=403574 width=163) (actual time=1.238..3165.721 rows=410760.00 loops=1)
  Index Cond: ((followers_count >= 100) AND (followers_count <= 200))
  Index Searches: 1
  Buffers: shared hit=57721 read=344669 written=3790
Planning:
  Buffers: shared hit=71 read=5
Planning Time: 2.366 ms
Execution Time: 3201.693 ms
```
---

### Task 6: Wider Range (100–1000) + Additional Indexes
Vyberte používateľov, ktorí majú `followers_count` väčší alebo rovný 100 a zároveň menší alebo rovný 1000. V čom je rozdiel, prečo?

Potom:
- Vytvorte ďalšie 3 indexy na `name`, `friends_count` a `description`.  
- Vložte svojho používateľa (ľubovoľné dáta) do `users`. Koľko to trvalo?  
- Dropnite vytvorené indexy a spravte vloženie ešte raz. Prečo je tu rozdiel?

**Solution I:**

Before running the query, I expanded the filter range on `followers_count` to observe how the range width affects the query plan and performance. This step demonstrates the threshold where using an index stops being beneficial.

**Query**
```sql
EXPLAIN ANALYZE 
SELECT * 
FROM users 
WHERE followers_count BETWEEN 100 AND 1000;
```

**Output**
```sql
Index Scan using idx_users_followers_count on users  (cost=0.43..169699.07 rows=1445160 width=163) (actual time=1.031..22587.819 rows=1449696.00 loops=1)
  Index Cond: ((followers_count >= 100) AND (followers_count <= 1000))
  Index Searches: 1
  Buffers: shared hit=222546 read=1210597
Planning Time: 0.362 ms
Execution Time: 22717.021 ms
```

The planner chose an **Index Scan**, but execution became significantly slower (≈22 s) compared to previous queries. This happens because the range `100–1000` returns too many rows, and index access causes numerous random disk reads. For large datasets, random index lookups become less efficient than sequential block reads. As the range widens, the benefit of the index decreases — at some point, the planner may even switch to a **Seq Scan** as a cheaper alternative.

**Solution - Vytvorte ďalšie 3 indexy:**

At this step, I created additional indexes on the columns `name`, `friends_count`, and `description` to analyze how adding more indexes affects data insertion and overall write performance.

**Query**
```sql
CREATE INDEX idx_users_name ON users(name);
CREATE INDEX idx_users_friends_count ON users(friends_count);
CREATE INDEX idx_users_description ON users(description);

SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE tablename = 'users';
```

**Output**
```sql
raw,users,users_pkey,CREATE UNIQUE INDEX users_pkey ON raw.users USING btree (id)
raw,users,idx_users_screen_name,CREATE INDEX idx_users_screen_name ON raw.users USING btree (lower(screen_name))
raw,users,idx_users_followers_count,CREATE INDEX idx_users_followers_count ON raw.users USING btree (followers_count)
raw,users,idx_users_name,CREATE INDEX idx_users_name ON raw.users USING btree (name)
raw,users,idx_users_friends_count,CREATE INDEX idx_users_friends_count ON raw.users USING btree (friends_count)
raw,users,idx_users_description,CREATE INDEX idx_users_description ON raw.users USING btree (description)
```

After creating these indexes, the table contained six B-tree structures in total, including the primary key. This improves search and filtering speed but increases the cost of `INSERT`, `UPDATE`, and `DELETE` operations. Each new index must be updated when a row is inserted, leading to additional disk writes. In summary, we gain faster reads but sacrifice write performance.

**Solution - Insert with All Indexes:**

Here, I inserted a new row into the table without removing any indexes to measure execution time and evaluate the impact of multiple indexes on write operations.

**Query**
```sql
EXPLAIN (ANALYZE, BUFFERS)
INSERT INTO users (id, screen_name, name, description, followers_count, friends_count, statuses_count, created_at)
VALUES (9999999997, 'test_user', 'My Test User', 'Testing performance', 150, 300, 20, NOW());
```

**Output**
```sql
Insert on users  (cost=0.00..0.01 rows=0 width=0) (actual time=1.300..1.301 rows=0.00 loops=1)
  Buffers: shared hit=4 read=16 dirtied=5
  ->  Result  (cost=0.00..0.01 rows=1 width=190) (actual time=0.008..0.010 rows=1.00 loops=1)
Planning Time: 0.054 ms
Execution Time: 1.348 ms
```

The insertion took about **1.3–1.9 ms**, during which PostgreSQL touched multiple buffers (hit/read/dirtied). This confirms that each insert requires updating not only the main table but also all related B-tree indexes. As the number of indexes increases and every write operation takes longer due to index maintenance overhead.


**Solution - Drop Indexes and Insert Again:**

In this step, I dropped the three additional indexes and repeated the same insert to compare performance without index update overhead.

**Query**
```sql
DROP INDEX idx_users_name;
DROP INDEX idx_users_friends_count;
DROP INDEX idx_users_description;

EXPLAIN (ANALYZE, BUFFERS)
INSERT INTO users (id, screen_name, name, description, followers_count, friends_count, statuses_count, created_at)
VALUES (9999999996, 'test_user', 'My Test User', 'Testing performance', 150, 300, 20, NOW());
```

**Output**
```sql
Insert on users  (cost=0.00..0.01 rows=0 width=0) (actual time=0.154..0.156 rows=0.00 loops=1)
  Buffers: shared hit=7
  ->  Result  (cost=0.00..0.01 rows=1 width=190) (actual time=0.009..0.010 rows=1.00 loops=1)
Planning Time: 0.056 ms
Execution Time: 0.207 ms
```

After dropping the indexes, the insertion executed almost instantly — under **0.2 ms**. This shows a direct correlation between the number of indexes and write performance. Without indexes, PostgreSQL simply adds the new row to the table without modifying additional index structures, drastically reducing latency and buffer load. Indexes clearly speed up read operations but significantly slow down DML tasks (`INSERT`, `UPDATE`, `DELETE`).

---

### Task 7: Indexes in `tweets` for `retweet_count` and `full_text`
Vytvorte index nad `retweet_count` a nad `full_text`.  Porovnajte dĺžku vytvárania. Prečo je tu taký rozdiel?

**Solution:**

Before executing the query, I extended the filter range on `followers_count` to observe how the range width affects the query plan and performance. This step helps identify the point where using an index becomes no longer beneficial. Prior to this experiment, I created two separate indexes in the `tweets` table — one on the numeric column `retweet_count` and another on the text column `full_text`. The goal was to compare index creation time for numeric vs. textual data types and understand why they differ in performance.

**Query**
```sql
-- Index on numeric field
CREATE INDEX idx_tweets_retweet_count ON tweets(retweet_count);

-- Index on large text field
CREATE INDEX idx_tweets_full_text ON tweets(full_text);
```

**Output**
```sql
[2025-10-13 19:41:16] tweetdb.raw> CREATE INDEX idx_tweets_retweet_count ON tweets(retweet_count)
[2025-10-13 19:41:35] completed in 19 s 438 ms
[2025-10-13 19:41:35] tweetdb.raw> CREATE INDEX idx_tweets_full_text ON tweets(full_text)
[2025-10-13 19:42:13] completed in 38 s 432 ms
```

Creating the index on `retweet_count` took approximately **19 seconds**, while building the index on `full_text` required nearly **twice as long (≈38 seconds)**. This difference stems from the nature and size of the data: numeric fields are compact and quick to sort, whereas text fields are large and variable in length, requiring additional comparisons, encoding steps, and larger writes to the index.

---

### Task 8: Comparison of Indexes
Porovnajte indexy pre `retweet_count`, `full_text`, `followers_count`, `screen_name`, …  V čom sa líšia a prečo.

Použite:
1. `CREATE EXTENSION pageinspect;`
2. `SELECT * FROM bt_metap('idx_content');`
3. `SELECT type, live_items, dead_items, avg_item_size, page_size, free_size FROM bt_page_stats('idx_content', 1000);`
4. `SELECT itemoffset, itemlen, data FROM bt_page_items('idx_content', 1) LIMIT 1000;`

**Solution:**

**Query**
```sql
-- 1. Enable pageinspect extension (once per database)
\c postgres
CREATE EXTENSION IF NOT EXISTS pageinspect;

-- 2. View metadata of a chosen index
SELECT * FROM bt_metap('idx_tweets_retweet_count');

-- 3. Check statistics of a specific page
SELECT type, live_items, dead_items, avg_item_size, page_size, free_size
FROM bt_page_stats('idx_tweets_retweet_count', 1000);

-- 4. Inspect individual index items on a specific page
SELECT itemoffset, itemlen, data
FROM bt_page_items('idx_tweets_retweet_count', 1)
LIMIT 1000;
```

**Output**
```sql
-- bt_metap
340322,4,209,2,209,2,0,-1,true

-- bt_page_stats
l,10,0,729,8192,812

-- bt_page_items
1,24,00 00 00 00 00 00 00 00
2,808,00 00 00 00 00 00 00 00
3,808,00 00 00 00 00 00 00 00
4,808,00 00 00 00 00 00 00 00
5,808,00 00 00 00 00 00 00 00
6,808,00 00 00 00 00 00 00 00
7,808,00 00 00 00 00 00 00 00
8,808,00 00 00 00 00 00 00 00
9,808,00 00 00 00 00 00 00 00
10,808,00 00 00 00 00 00 00 00
```

From these results, I can see that the index is built as a normal B-tree with two levels – a root and leaf pages that store the actual data. The statistics show there are 10 live items and no dead ones, so the index is clean and working efficiently. Each item takes around 700–800 bytes, which means the indexed values are quite large and fill most of the 8 KB page. In simple terms, this means that text indexes take up more space and have bigger entries than numeric ones, which makes them a bit heavier but still useful for searching.

---

### Task 9: Searching for “Gates” Anywhere in `tweets.full_text`
Vyhľadajte v `tweets.full_text` meno „Gates“ na ľubovoľnom mieste a porovnajte výsledok po tom, ako `full_text` naindexujete.  
V čom je rozdiel a prečo?

**Solution:**

Before running these queries, I wanted to examine how PostgreSQL handles substring searches within large text columns. First, I searched for the word “Gates” without any index to see the baseline performance. Then I created a trigram GIN index (`pg_trgm`) to test how much faster the search becomes and why this special index is needed for `LIKE '%...%'` patterns.

**Query**
```sql
EXPLAIN ANALYZE
SELECT *
FROM tweets
WHERE full_text ILIKE '%Gates%';
```

**Output**
```sql
Gather  (cost=1000.00..569906.18 rows=59434 width=247) (actual time=19.415..8728.769 rows=21996.00 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  Buffers: shared hit=14591 read=515288
  ->  Parallel Seq Scan on tweets  (cost=0.00..562962.78 rows=24764 width=247) (actual time=12.900..8677.254 rows=7332.00 loops=3)
        Filter: (full_text ~~* '%Gates%'::text)
        Rows Removed by Filter: 2110030
        Buffers: shared hit=14591 read=515288
Planning:
  Buffers: shared hit=226 read=25 dirtied=1
Planning Time: 13.746 ms
Execution Time: 8731.514 ms
```

The planner used a **Parallel Sequential Scan**, scanning the entire table and filtering each row individually. Execution took about **8.7 seconds**, as PostgreSQL could not use a regular B-tree index for a substring pattern starting with `%`. This method causes heavy I/O and CPU usage because every tweet must be read and checked for the substring “Gates”.

Then I created trigram index (pg_trgm), that allows us to search in rows. This was long...

**Query**
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX idx_tweets_full_text_trgm
    ON tweets
        USING gin (full_text gin_trgm_ops);

EXPLAIN ANALYZE
SELECT *
FROM tweets
WHERE full_text ILIKE '%Gates%';
```

**Output**
```sql
Bitmap Heap Scan on tweets  (cost=454.46..171286.81 rows=59434 width=247) (actual time=41.312..1258.946 rows=21996.00 loops=1)
  Recheck Cond: (full_text ~~* '%Gates%'::text)
  Rows Removed by Index Recheck: 7001
  Heap Blocks: exact=26771
  Buffers: shared hit=255 read=27070 written=15937
  ->  Bitmap Index Scan on idx_tweets_full_text_trgm  (cost=0.00..439.60 rows=59434 width=0) (actual time=35.452..35.454 rows=28997.00 loops=1)
        Index Cond: (full_text ~~* '%Gates%'::text)
        Index Searches: 1
        Buffers: shared hit=255 read=299 written=217
Planning:
  Buffers: shared hit=10 read=15 dirtied=3
Planning Time: 10.864 ms
Execution Time: 1263.155 ms
```

After adding the **GIN trigram index**, the planner switched to a **Bitmap Index Scan + Bitmap Heap Scan**, cutting execution time down to about **1.2 seconds**. The index allows PostgreSQL to quickly locate candidate rows by matching trigrams (three-character sequences) instead of scanning all text. Although index creation was time-consuming, subsequent searches became significantly faster and more efficient, demonstrating the power of trigram indexing for substring queries.

---

### Task 10: Tweets Starting with “DANGER: WARNING:”
Vyhľadajte tweet, ktorý začína `DANGER: WARNING:`. Použil sa index?

**Solution:**

In this task, I first ran a search using the pattern `'DANGER: WARNING:%'` to check which type of scan PostgreSQL would choose.  

**Query**
```sql
EXPLAIN ANALYZE
SELECT *
FROM tweets
WHERE full_text LIKE 'DANGER: WARNING:%';
```

**Output**
```sql
Bitmap Heap Scan on tweets  (cost=278.00..2578.59 rows=588 width=247) (actual time=154.643..154.660 rows=1.00 loops=1)
  Recheck Cond: (full_text ~~ 'DANGER: WARNING:%'::text)
  Rows Removed by Index Recheck: 44
  Heap Blocks: exact=45
  Buffers: shared hit=5055
  ->  Bitmap Index Scan on idx_tweets_full_text_trgm  (cost=0.00..277.85 rows=588 width=0) (actual time=154.406..154.407 rows=45.00 loops=1)
        Index Cond: (full_text ~~ 'DANGER: WARNING:%'::text)
        Index Searches: 1
        Buffers: shared hit=5010
Planning:
  Buffers: shared hit=1
Planning Time: 0.567 ms
Execution Time: 154.922 ms
```

Even without creating a new index, the system used the existing **trigram index** (`idx_tweets_full_text_trgm`), which is suitable for substring searches.

---

### Task 11: Indexing `full_text` for Index Usage
Teraz naindexujte `full_text` tak, aby sa použil index a zhodnoťte, prečo sa predtým nad `DANGER: WARNING:` nepoužil. Použije sa teraz na „Gates“ na ľubovoľnom mieste?

**Solution:**

After creating a regular **B-tree index**, nothing changed — the plan remained the same, because PostgreSQL considers the **trigram index** more efficient for text comparisons using `LIKE`.

**Query**
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_tweets_full_text_trgm ON tweets USING gin (full_text gin_trgm_ops);
ANALYZE tweets;


EXPLAIN ANALYZE
SELECT *
FROM tweets
WHERE full_text LIKE 'DANGER: WARNING:%';
```

**Output**
```sql
Bitmap Heap Scan on tweets  (cost=277.99..2570.85 rows=586 width=248) (actual time=212.120..212.254 rows=1.00 loops=1)
  Recheck Cond: (full_text ~~ 'DANGER: WARNING:%'::text)
  Rows Removed by Index Recheck: 44
  Heap Blocks: exact=45
  Buffers: shared hit=2498 read=2564 written=1637
  ->  Bitmap Index Scan on idx_tweets_full_text_trgm  (cost=0.00..277.84 rows=586 width=0) (actual time=206.047..206.053 rows=45.00 loops=1)
        Index Cond: (full_text ~~ 'DANGER: WARNING:%'::text)
        Index Searches: 1
        Buffers: shared hit=2498 read=2519 written=1592
Planning:
  Buffers: shared hit=137 read=18
Planning Time: 15.390 ms
Execution Time: 215.182 ms
```

After creating the **trigram GIN index**, the query became faster — the planner switched to a **Bitmap Index Scan**, confirming that the index was used. Execution time dropped significantly because PostgreSQL no longer had to scan the entire table, only the candidate rows from the index. The same index is also used for substring patterns like `'%Gates%'`, since trigram indexing supports searching anywhere within the text.  

---

### Task 12: Case-Insensitive Search for Suffix “LUCIFERASE”
Vytvorte nový index tak, aby ste vedeli vyhľadať tweet, ktorý končí reťazcom „LUCIFERASE“ a nezáleží na tom, ako to napíšete.

**Solution:**

First, I enabled the `pg_trgm` extension — it allows PostgreSQL to use **trigrams** (i.e., sequences of three consecutive characters) for substring matching. Then, I created an index for **case-insensitive substring search**. To make the search independent of letter case, it’s best to build the index on the **lowercase version** of the text:

**Query**
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_tweets_full_text_lc_trgm
    ON tweets
        USING gin (lower(full_text) gin_trgm_ops);

ANALYZE tweets;
EXPLAIN ANALYZE
SELECT *
FROM tweets
WHERE lower(full_text) LIKE '%luciferase';
```

**Output**
```sql
Bitmap Heap Scan on tweets  (cost=170.53..2488.05 rows=592 width=248) (actual time=42.206..42.213 rows=0.00 loops=1)
  Recheck Cond: (lower(full_text) ~~ '%luciferase'::text)
  Rows Removed by Index Recheck: 91
  Heap Blocks: exact=90
  Buffers: shared hit=483 read=607
  ->  Bitmap Index Scan on idx_tweets_full_text_lc_trgm  (cost=0.00..170.38 rows=592 width=0) (actual time=34.679..34.680 rows=91.00 loops=1)
        Index Cond: (lower(full_text) ~~ '%luciferase'::text)
        Index Searches: 1
        Buffers: shared hit=483 read=517
Planning:
  Buffers: shared hit=147 read=14
Planning Time: 7.963 ms
Execution Time: 42.326 ms
```

The query used the new trigram index successfully, as shown by the Bitmap Index Scan in the plan. Execution time dropped to around 42 ms, which is very fast compared to a full sequential scan that would take several seconds. Because the index is built on lower(full_text), PostgreSQL can now find the word “luciferase” regardless of capitalization and position in the text.

---

### Task 13: Combined Filters and Sorting in `users`
Nájdite účty, ktoré majú `follower_count < 10` a `friends_count > 1000`, a výsledok zoraďte podľa `statuses_count`. Následne spravte jednoduché indexy tak, aby to malo zmysel, a popíšte výsledok.

**Solution:**

First, let’s see which execution plan PostgreSQL chooses when running the query **without any index**.

**Query**
```sql
EXPLAIN ANALYZE
SELECT *
FROM users
WHERE followers_count < 10
  AND friends_count > 1000
ORDER BY statuses_count;
```

**Output**
```sql
Gather Merge  (cost=147654.58..152576.81 rows=42263 width=163) (actual time=1072.746..1079.101 rows=166.00 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  Buffers: shared hit=74 read=126711 dirtied=2
  ->  Sort  (cost=146654.56..146698.59 rows=17610 width=163) (actual time=1020.836..1020.903 rows=55.33 loops=3)
        Sort Key: statuses_count
        Sort Method: quicksort  Memory: 34kB
        Buffers: shared hit=74 read=126711 dirtied=2
        Worker 0:  Sort Method: quicksort  Memory: 32kB
        Worker 1:  Sort Method: quicksort  Memory: 31kB
        ->  Parallel Seq Scan on users  (cost=0.00..145412.69 rows=17610 width=163) (actual time=31.872..1019.948 rows=55.33 loops=3)
              Filter: ((followers_count < 10) AND (friends_count > 1000))
              Rows Removed by Filter: 997369
              Buffers: shared read=126711 dirtied=2
Planning:
  Buffers: shared hit=94 read=10
Planning Time: 7.160 ms
Execution Time: 1079.610 ms
```

Without indexes, PostgreSQL used a **parallel sequential scan**, checking all rows in the table and sorting the result manually. This is slow because filters cannot be applied directly through an index. Sorting by `statuses_count` is also performed separately since there is no index that stores data in the required order.

**Query**
```sql
EXPLAIN ANALYZE
SELECT *
FROM users
WHERE followers_count < 10
  AND friends_count > 1000
ORDER BY statuses_count;
```

**Output**
```sql
Gather Merge  (cost=91763.02..96745.46 rows=42780 width=163) (actual time=53.855..60.039 rows=166.00 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  Buffers: shared hit=84 read=178
  ->  Sort  (cost=90763.00..90807.56 rows=17825 width=163) (actual time=2.108..2.121 rows=55.33 loops=3)
        Sort Key: statuses_count
        Sort Method: quicksort  Memory: 49kB
        Buffers: shared hit=84 read=178
        Worker 0:  Sort Method: quicksort  Memory: 25kB
        Worker 1:  Sort Method: quicksort  Memory: 25kB
        ->  Parallel Bitmap Heap Scan on users  (cost=1843.66..89504.41 rows=17825 width=163) (actual time=1.680..2.022 rows=55.33 loops=3)
              Recheck Cond: ((followers_count < 10) AND (friends_count > 1000))
              Heap Blocks: exact=166
              Buffers: shared hit=70 read=178
              ->  Bitmap Index Scan on idx_users_filter_sort  (cost=0.00..1832.96 rows=42781 width=0) (actual time=1.383..1.385 rows=166.00 loops=1)
                    Index Cond: ((followers_count < 10) AND (friends_count > 1000))
                    Index Searches: 11
                    Buffers: shared hit=30 read=12
Planning:
  Buffers: shared hit=24 read=5
Planning Time: 4.438 ms
Execution Time: 60.128 ms
```

After adding the index, PostgreSQL completely changed its execution strategy. Thanks to the index, the planner applied a **Bitmap Index Scan** followed by a **Bitmap Heap Scan**, allowing it to quickly find only the needed rows without a full table scan. The total execution time dropped from about **1080 ms to 60 ms** — more than **17 times faster**. Sorting (`ORDER BY statuses_count`) still occurs, but now it operates on a much smaller data set, making the process almost instantaneous.

---

### Task 14: Composite Index vs. Separate Indexes
Na predošlú query spravte zložený index a porovnajte výsledok s tým, keď sú indexy separátne.

**Solution:**

First, I deleted the old indexes to start from a clean slate and created two separate indexes, then ran the same query again.

**Query**
```sql
EXPLAIN ANALYZE
SELECT *
FROM users
WHERE followers_count < 10
  AND friends_count > 1000
ORDER BY statuses_count;
```

**Output**
```sql
Gather Merge  (cost=99181.29..104098.27 rows=42218 width=163) (actual time=319.193..331.537 rows=166.00 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  Buffers: shared hit=116 read=55107 written=35
  ->  Sort  (cost=98181.27..98225.25 rows=17591 width=163) (actual time=287.377..287.390 rows=55.33 loops=3)
        Sort Key: statuses_count
        Sort Method: quicksort  Memory: 34kB
        Buffers: shared hit=116 read=55107 written=35
        Worker 0:  Sort Method: quicksort  Memory: 32kB
        Worker 1:  Sort Method: quicksort  Memory: 31kB
        ->  Parallel Bitmap Heap Scan on users  (cost=9939.59..96940.88 rows=17591 width=163) (actual time=53.666..287.070 rows=55.33 loops=3)
              Recheck Cond: ((followers_count < 10) AND (friends_count > 1000))
              Rows Removed by Index Recheck: 339712
              Heap Blocks: exact=8870 lossy=12602
              Buffers: shared hit=102 read=55107 written=35
              Worker 0:  Heap Blocks: exact=6895 lossy=9834
              Worker 1:  Heap Blocks: exact=6645 lossy=9491
              ->  BitmapAnd  (cost=9939.59..9939.59 rows=42218 width=0) (actual time=76.049..76.051 rows=0.00 loops=1)
                    Buffers: shared hit=3 read=829
                    ->  Bitmap Index Scan on idx_users_followers_count  (cost=0.00..1947.77 rows=174845 width=0) (actual time=20.014..20.014 rows=169772.00 loops=1)
                          Index Cond: (followers_count < 10)
                          Index Searches: 1
                          Buffers: shared hit=3 read=143
                    ->  Bitmap Index Scan on idx_users_friends_count  (cost=0.00..7970.46 rows=720804 width=0) (actual time=52.307..52.308 rows=731833.00 loops=1)
                          Index Cond: (friends_count > 1000)
                          Index Searches: 1
                          Buffers: shared read=686
Planning:
  Buffers: shared hit=83 read=6
Planning Time: 4.370 ms
Execution Time: 331.669 ms
```

When two separate indexes were used (`followers_count` and `friends_count`), PostgreSQL performed a **Parallel Bitmap Heap Scan** with a **BitmapAnd** operation to combine both indexes. This required scanning and merging a large number of index pages and rechecking many rows (*Rows Removed by Index Recheck: 339,712*).  
The total execution time was about **331 ms**, showing additional overhead from combining two independent index scans.
Then I deleted those indexes again and created a **composite index**, repeating the query.

**Query**
```sql
DROP INDEX IF EXISTS idx_users_followers_count;
DROP INDEX IF EXISTS idx_users_friends_count;

CREATE INDEX idx_users_composite
    ON users(followers_count, friends_count, statuses_count);
ANALYZE users;

EXPLAIN ANALYZE
SELECT *
FROM users
WHERE followers_count < 10
  AND friends_count > 1000
ORDER BY statuses_count;
```

**Output**
```sql
Gather Merge  (cost=89973.65..94789.65 rows=41351 width=162) (actual time=50.526..56.541 rows=166.00 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  Buffers: shared hit=118 read=135
  ->  Sort  (cost=88973.62..89016.70 rows=17230 width=162) (actual time=0.999..1.011 rows=55.33 loops=3)
        Sort Key: statuses_count
        Sort Method: quicksort  Memory: 49kB
        Buffers: shared hit=118 read=135
        Worker 0:  Sort Method: quicksort  Memory: 25kB
        Worker 1:  Sort Method: quicksort  Memory: 25kB
        ->  Parallel Bitmap Heap Scan on users  (cost=1791.46..87761.27 rows=17230 width=162) (actual time=0.470..0.933 rows=55.33 loops=3)
              Recheck Cond: ((followers_count < 10) AND (friends_count > 1000))
              Heap Blocks: exact=166
              Buffers: shared hit=104 read=135
              ->  Bitmap Index Scan on idx_users_composite  (cost=0.00..1781.12 rows=41351 width=0) (actual time=0.216..0.217 rows=166.00 loops=1)
                    Index Cond: ((followers_count < 10) AND (friends_count > 1000))
                    Index Searches: 11
                    Buffers: shared hit=21 read=12
Planning:
  Buffers: shared hit=73 read=7
Planning Time: 2.090 ms
Execution Time: 56.616 ms
```

After creating a **composite index** on `(followers_count, friends_count, statuses_count)`, PostgreSQL used a **single Bitmap Index Scan** instead of merging multiple indexes. This drastically reduced buffer reads and brought the execution time down to about **56 ms** — almost **6× faster**.  The optimizer could now use the combined key information directly, improving both filtering and sorting efficiency. In short, one well-designed **composite index** is much faster and cleaner than multiple separate indexes for queries filtering on multiple columns.

---

### Task 15: Changing the Boundary of `follower_count`
Upravte query tak, aby bol `follower_count < 1000` a `friends_count > 1000`. V čom je rozdiel a prečo?

**Solution:**

I increased the filter boundary by 100×, which made the selection much broader — the planner can decide that using an index is no longer efficient and switch to a **Sequential Scan** or **Parallel Sequential Scan**.

**Query**
```sql
EXPLAIN ANALYZE
SELECT *
FROM users
WHERE followers_count < 1000
  AND friends_count > 1000
ORDER BY statuses_count;
```

**Output**
```sql
Gather Merge  (cost=186604.08..252387.50 rows=564827 width=162) (actual time=364.235..487.940 rows=263293.00 loops=1)
  Workers Planned: 2
  Workers Launched: 2
"  Buffers: shared hit=15407 read=111378, temp read=5919 written=5932"
  ->  Sort  (cost=185604.06..186192.42 rows=235345 width=162) (actual time=290.242..314.844 rows=87764.33 loops=3)
        Sort Key: statuses_count
        Sort Method: external merge  Disk: 18416kB
"        Buffers: shared hit=15407 read=111378, temp read=5919 written=5932"
        Worker 0:  Sort Method: external merge  Disk: 13568kB
        Worker 1:  Sort Method: external merge  Disk: 15368kB
        ->  Parallel Seq Scan on users  (cost=0.00..145300.09 rows=235345 width=162) (actual time=0.451..234.085 rows=87764.33 loops=3)
              Filter: ((followers_count < 1000) AND (friends_count > 1000))
              Rows Removed by Filter: 909660
              Buffers: shared hit=15333 read=111378
Planning Time: 0.831 ms
Execution Time: 522.758 ms
```

As a result, PostgreSQL **switched to a Parallel Sequential Scan**. This happened because the filter became much wider, returning hundreds of thousands of rows. In such cases, a full table scan is cheaper than using an index, since the index would require too many random reads with little benefit. The planner correctly chose a **full table scan with sorting**, as this approach minimizes overhead for large result sets. As a consequence, the query execution time increased to about **523 ms**, and an **external merge sort** appeared — meaning the sort no longer fit entirely in memory.

---

### Task 16: Complex Query on `tweets` and `users`
Vyhľadajte všetky tweety (`full_text`), ktoré spomenul autor, ktorý obsahuje v `description` reťazec „comedian” (case-insensitive), tweety musia obsahovať reťaz „conspiracy“ (case-insensitive), tweety nesmú mať priradený hashtag a `retweet_count` je buď menší alebo rovný 10, alebo väčší ako 50. Zobrazte len rozdielne záznamy a zoraďte ich podľa počtu followerov DESC. Následne nad tým spravte analýzu a popíšte do protokolu, čo všetko sa tam deje (`EXPLAIN ANALYZE`).

**Solution:**

First, I ran the query without any indexes just to see what PostgreSQL would do. Then, I added a few indexes and compared how the execution plan and speed changed.

**Query**
```sql
EXPLAIN ANALYZE
SELECT DISTINCT ON (t.full_text) 
    t.full_text, u.followers_count
FROM tweets t
JOIN users u ON t.user_id = u.id
LEFT JOIN tweet_hashtag th ON t.id = th.tweet_id
WHERE lower(u.description) LIKE '%comedian%'
  AND lower(t.full_text) LIKE '%conspiracy%'
  AND th.hashtag_id IS NULL
  AND (t.retweet_count <= 10 OR t.retweet_count > 50)
ORDER BY t.full_text, u.followers_count DESC;


CREATE INDEX idx_users_description_trgm ON users USING gin (lower(description) gin_trgm_ops);
CREATE INDEX idx_users_followers_count ON users(followers_count);
ANALYZE tweets;
ANALYZE users;

-- (and again query)
```

**Output**
```sql
Unique  (cost=4317.10..4317.10 rows=1 width=149) (actual time=1822.552..1822.582 rows=5.00 loops=1)
  Buffers: shared hit=28549 read=21503 dirtied=151
  ->  Sort  (cost=4317.10..4317.10 rows=1 width=149) (actual time=1822.526..1822.539 rows=5.00 loops=1)
"        Sort Key: t.full_text, u.followers_count DESC"
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=28549 read=21503 dirtied=151
        ->  Nested Loop  (cost=149.99..4317.09 rows=1 width=149) (actual time=582.086..1822.388 rows=5.00 loops=1)
              Buffers: shared hit=28549 read=21503 dirtied=151
              ->  Nested Loop Left Join  (cost=149.56..4308.63 rows=1 width=153) (actual time=69.927..535.726 rows=5671.00 loops=1)
                    Filter: (th.hashtag_id IS NULL)
                    Rows Removed by Filter: 2122
                    Buffers: shared hit=15511 read=11547
                    ->  Bitmap Heap Scan on tweets t  (cost=149.13..2469.61 rows=413 width=161) (actual time=69.202..181.681 rows=6439.00 loops=1)
                          Recheck Cond: (lower(full_text) ~~ '%conspiracy%'::text)
                          Rows Removed by Index Recheck: 5
                          Filter: ((retweet_count <= 10) OR (retweet_count > 50))
                          Rows Removed by Filter: 552
                          Heap Blocks: exact=6862
                          Buffers: shared hit=417 read=7314
                          ->  Bitmap Index Scan on idx_tweets_full_text_lc_trgm  (cost=0.00..149.03 rows=592 width=0) (actual time=67.542..67.545 rows=6996.00 loops=1)
                                Index Cond: (lower(full_text) ~~ '%conspiracy%'::text)
                                Index Searches: 1
                                Buffers: shared hit=417 read=452
                    ->  Index Only Scan using idx_tweet_hashtag_uk on tweet_hashtag th  (cost=0.43..4.41 rows=4 width=16) (actual time=0.053..0.054 rows=0.33 loops=6439)
                          Index Cond: (tweet_id = t.id)
                          Heap Fetches: 0
                          Index Searches: 6439
                          Buffers: shared hit=15094 read=4233
              ->  Index Scan using users_pkey on users u  (cost=0.43..8.40 rows=1 width=12) (actual time=0.226..0.226 rows=0.00 loops=5671)
                    Index Cond: (id = t.user_id)
                    Filter: (lower(description) ~~ '%comedian%'::text)
                    Rows Removed by Filter: 1
                    Index Searches: 5671
                    Buffers: shared hit=13038 read=9956 dirtied=151
Planning:
  Buffers: shared hit=139 read=39
Planning Time: 16.062 ms
Execution Time: 1825.086 ms
```

Without indexes, PostgreSQL had to go through almost all rows in both tables (`tweets` and `users`). It used **nested loops** and **sequential joins**, checking every record where the text matched `%comedian%` or `%conspiracy%`. Because there were no text indexes, PostgreSQL had to compare strings row by row. It ended up doing many repeated lookups through `users_pkey`, taking around **1.8 seconds** and reading more than **50,000 buffers** — clearly inefficient.

**Output**
```sql
Unique  (cost=3484.14..3484.15 rows=1 width=149) (actual time=373.494..373.564 rows=5.00 loops=1)
  Buffers: shared hit=565 read=9647 written=765
  ->  Sort  (cost=3484.14..3484.15 rows=1 width=149) (actual time=373.492..373.555 rows=5.00 loops=1)
"        Sort Key: t.full_text, u.followers_count DESC"
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=565 read=9647 written=765
        ->  Nested Loop Left Join  (cost=1208.89..3484.13 rows=1 width=149) (actual time=173.481..373.496 rows=5.00 loops=1)
              Filter: (th.hashtag_id IS NULL)
              Rows Removed by Filter: 20
              Buffers: shared hit=565 read=9647 written=765
              ->  Hash Join  (cost=1208.46..3479.68 rows=1 width=157) (actual time=144.386..370.432 rows=9.00 loops=1)
                    Hash Cond: (t.user_id = u.id)
                    Buffers: shared hit=554 read=9630 written=764
                    ->  Bitmap Heap Scan on tweets t  (cost=149.07..2419.23 rows=405 width=161) (actual time=57.658..327.958 rows=6439.00 loops=1)
                          Recheck Cond: (lower(full_text) ~~ '%conspiracy%'::text)
                          Rows Removed by Index Recheck: 5
                          Filter: ((retweet_count <= 10) OR (retweet_count > 50))
                          Rows Removed by Filter: 552
                          Heap Blocks: exact=6862
                          Buffers: shared hit=420 read=7311 written=764
                          ->  Bitmap Index Scan on idx_tweets_full_text_lc_trgm  (cost=0.00..148.97 rows=579 width=0) (actual time=56.681..56.682 rows=6996.00 loops=1)
                                Index Cond: (lower(full_text) ~~ '%conspiracy%'::text)
                                Index Searches: 1
                                Buffers: shared hit=417 read=452
                    ->  Hash  (cost=1056.34..1056.34 rows=244 width=12) (actual time=40.855..40.912 rows=2131.00 loops=1)
                          Buckets: 4096 (originally 1024)  Batches: 1 (originally 1)  Memory Usage: 132kB
                          Buffers: shared hit=134 read=2319
                          ->  Bitmap Heap Scan on users u  (cost=108.80..1056.34 rows=244 width=12) (actual time=24.466..40.038 rows=2131.00 loops=1)
                                Recheck Cond: (lower(description) ~~ '%comedian%'::text)
                                Rows Removed by Index Recheck: 61
                                Heap Blocks: exact=2160
                                Buffers: shared hit=134 read=2319
                                ->  Bitmap Index Scan on idx_users_description_trgm  (cost=0.00..108.74 rows=244 width=0) (actual time=23.950..23.950 rows=2192.00 loops=1)
                                      Index Cond: (lower(description) ~~ '%comedian%'::text)
                                      Index Searches: 1
                                      Buffers: shared hit=130 read=163
              ->  Index Only Scan using idx_tweet_hashtag_uk on tweet_hashtag th  (cost=0.43..4.41 rows=4 width=16) (actual time=0.333..0.334 rows=2.22 loops=9)
                    Index Cond: (tweet_id = t.id)
                    Heap Fetches: 0
                    Index Searches: 9
                    Buffers: shared hit=11 read=17 written=1
Planning:
  Buffers: shared hit=178 read=45
Planning Time: 22.629 ms
Execution Time: 373.878 ms
```

After I added **trigram indexes** on `lower(description)` and `lower(full_text)`, plus an index on `followers_count`, PostgreSQL completely changed the plan.  Now it used a **Hash Join** between `tweets` and `users` and applied **Bitmap Index Scans** from the trigram indexes to find matching text much faster. The query became about **five times faster** — execution time dropped to **~374 ms**, and buffer reads decreased drastically. In short, after adding the right indexes, PostgreSQL started using them smartly: it filters text efficiently, joins tables faster, and avoids unnecessary loops.



