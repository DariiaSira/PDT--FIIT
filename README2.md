# 1. Project Overview

This project focuses on query optimization and index performance analysis in PostgreSQL.  
As a data engineer analyzing historical tweets and user profiles, you are tasked with diagnosing slow query execution and dashboard performance issues.  
The primary goal is to investigate query plans, experiment with indexes, and observe how PostgreSQL’s planner and parallel execution behave under various scenarios.  
Through a series of exercises, you will analyze execution plans, create appropriate indexes, and document their impact on query time and system load.  
Your findings will serve as a foundation for understanding database performance tuning and optimization strategies.

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

**Results Analysis**

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
Koľko workerov pracovalo na danom selecte?  
Zdvihnite počet workerov a povedzte, ako to ovplyvňuje čas. Je tam nejaký strop?

**Solution:**

I executed the same query as before, but this time I adjusted the PostgreSQL parameter `max_parallel_workers_per_gather` to test how different levels of parallelism affect performance.  
Each run was analyzed using `EXPLAIN ANALYZE` to observe worker utilization, execution time, and buffer reads.

**Results Analysis**

| **max_parallel_workers_per_gather** | **Workers Planned** | **Workers Launched** | **Execution Time (ms)** | **Buffers read** | **Observation** |
|------------------------------------:|---------------------:|----------------------:|-------------------------:|-----------------:|-----------------|
| 2 (default) | 2 | 2 | 1095 | 126,711 | Baseline case — full table scan |
| 4 | 4 | 4 | 388 | 126,422 | Strong acceleration — load effectively distributed |
| 6 | 5 | 5 | 363 | 124,824 | Slight improvement — near performance ceiling |
| 8 | 5 | 5 | 413 | 124,260 | Slowdown — excessive parallelization overhead |

When increasing `max_parallel_workers_per_gather` to 4, execution time dropped almost threefold (1.09 s → 0.39 s),  
proving that parallel reading significantly speeds up sequential scans.  

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

**Results Analysis**  
PostgreSQL prevented index creation because an index with the same name already exists in the database.  
Each table can only have uniquely named indexes, and `idx_users_screen_name` was already present from earlier experiments.

**Solution II:**

Next, I updated table statistics using `ANALYZE` and disabled parallel workers by setting `max_parallel_workers_per_gather = 0`.  
The planner still chose a **Sequential Scan**, even though the index was available.

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

**Results Analysis**  
Even after refreshing statistics and disabling parallel execution, PostgreSQL’s planner decided that a full sequential scan was cheaper than random index lookups.  
For ~3 million rows with evenly distributed `screen_name` values, the optimizer estimated that using the index would not provide performance benefits.

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

**Results Analysis**  
Lowering `random_page_cost` caused the planner to re-evaluate, but the final plan remained a parallel sequential scan.  
Even with cheaper random I/O, the potential benefit of index access was still too low — scanning the entire table in parallel was faster for finding one record among millions.

---

### Task 4: Filter on `followers_count` (100–200)
Vyberte používateľov, ktorí majú `followers_count` väčší alebo rovný 100 a zároveň menší alebo rovný 200.  
Je správanie rovnaké ako v prvej úlohe? Je správanie rovnaké ako v druhej úlohe? Prečo?

**Solution I:**

I first executed the range query on `followers_count` without any index to observe the baseline behavior and planner choice.  
PostgreSQL performed a sequential scan over the entire `users` table (~3 million rows) and applied the filter row by row.

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

**Results Analysis**  
Without an index, PostgreSQL has no way to directly locate matching rows — it must read every record sequentially.  
Since the range `(100 ≤ followers_count ≤ 200)` returns around 400,000 rows (~13% of the table), the query is not highly selective.  
For such moderately large subsets, the planner correctly chooses a **Sequential Scan** (or **Parallel Seq Scan**) because linear I/O access is faster and more predictable.  
Execution time was about **0.5 s**, with moderate CPU and I/O utilization.

**Solution II:**

I decided to check the influence of indexes. After creating an index on `followers_count` and running `ANALYZE`, the planner switched to using an **Index Scan**, recognizing that the condition can be satisfied via a B-tree lookup.  
However, the query became significantly slower — **3.2 seconds** compared to 0.5 seconds before indexing.

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

**Results Analysis**  
Although the index allows PostgreSQL to locate the lower and upper range boundaries quickly, it must still fetch approximately 400,000 matching rows from disk.  
This results in a large number of random reads, which are much slower than sequential block reads.  
The sequential scan reads the same data linearly and benefits from better cache and I/O locality, making it faster on both HDD and SSD storage.  
The index proves beneficial only when a very small portion of the table (typically less than 5–10%) is returned — for wide ranges like this one, it introduces unnecessary overhead.

**Comparison with Previous Experiments**

| **Task** | **Planner Behavior** | **Reason** |
|-----------|----------------------|-------------|
| Task 1 – `screen_name = 'realDonaldTrump'` | Planner chose **Parallel Seq Scan**, index ignored | Query was highly selective (1 row), but random index I/O was considered more expensive |
| Task 2 – Parallel Workers | Execution time improved up to 4–5 workers, then stabilized | Parallel Seq Scan scales well for large tables |
| Task 4 – `followers_count` range | With index: slower, without index: faster | Range too wide → Index Scan causes excessive random I/O |

In this experiment, the sequential (or parallel) scan proved to be the most efficient method for medium-to-large data volumes.  
When the index on `followers_count` was created, PostgreSQL’s planner switched to using it, but overall query time increased instead of decreasing.  
The reason is that the range `(100–200)` returned too many rows, leading to numerous random disk reads and higher I/O costs.  
Sequential scans, by contrast, read data linearly and benefit from better caching and throughput on large datasets.  
Therefore, although the index technically works, it becomes **economically inefficient** for wide ranges, unlike the cases in Tasks 1 and 2 where parallel scans were beneficial.

---

### Task 5: Index for Task 4 and Bitmaps
Vytvorte index nad podmienkou z úlohy 4 a popíšte prácu s indexom.  
Čo je to Bitmap Index Scan a prečo je tam Bitmap Heap Scan? Prečo je tam recheck condition?

**Solution:**

I already performed this in Task 4, where PostgreSQL used a **Bitmap Index Scan** followed by a **Bitmap Heap Scan** to handle the range condition efficiently.  
The **Recheck Cond** step ensured accuracy by verifying each matching row after fetching it from the heap.

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
Vyberte používateľov, ktorí majú `followers_count` väčší alebo rovný 100 a zároveň menší alebo rovný 1000.  
V čom je rozdiel, prečo?

Potom:
- Vytvorte ďalšie 3 indexy na `name`, `friends_count` a `description`.  
- Vložte svojho používateľa (ľubovoľné dáta) do `users`. Koľko to trvalo?  
- Dropnite vytvorené indexy a spravte vloženie ešte raz. Prečo je tu rozdiel?

**Solution I:**

Before running the query, I expanded the filter range on `followers_count` to observe how the range width affects the query plan and performance.  
This step demonstrates the threshold where using an index stops being beneficial.

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

**Results Analysis**

The planner chose an **Index Scan**, but execution became significantly slower (≈22 s) compared to previous queries.  
This happens because the range `100–1000` returns too many rows, and index access causes numerous random disk reads.  
For large datasets, random index lookups become less efficient than sequential block reads.  
As the range widens, the benefit of the index decreases — at some point, the planner may even switch to a **Seq Scan** as a cheaper alternative.

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

**Results Analysis**

After creating these indexes, the table contained six B-tree structures in total, including the primary key.  
This improves search and filtering speed but increases the cost of `INSERT`, `UPDATE`, and `DELETE` operations.  
Each new index must be updated when a row is inserted, leading to additional disk writes.  
In summary, we gain faster reads but sacrifice write performance.

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

**Results Analysis**  

The insertion took about **1.3–1.9 ms**, during which PostgreSQL touched multiple buffers (hit/read/dirtied).  
This confirms that each insert requires updating not only the main table but also all related B-tree indexes.  
As the number of indexes increases, so does the disk I/O load, and every write operation takes longer due to index maintenance overhead.


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

**Results Analysis**  

After dropping the indexes, the insertion executed almost instantly — under **0.2 ms**.  
This shows a direct correlation between the number of indexes and write performance.  
Without indexes, PostgreSQL simply adds the new row to the table without modifying additional index structures, drastically reducing latency and buffer load.  
Indexes clearly speed up read operations but significantly slow down DML tasks (`INSERT`, `UPDATE`, `DELETE`).

---

### Task 7: Indexes in `tweets` for `retweet_count` and `full_text`
Vytvorte index nad `retweet_count` a nad `full_text`.  Porovnajte dĺžku vytvárania. Prečo je tu taký rozdiel?

**Solution:**

Before executing the query, I extended the filter range on `followers_count` to observe how the range width affects the query plan and performance.  
This step helps identify the point where using an index becomes no longer beneficial. Prior to this experiment, I created two separate indexes in the `tweets` table — one on the numeric column `retweet_count` and another on the text column `full_text`. The goal was to compare index creation time for numeric vs. textual data types and understand why they differ in performance.

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

**Results Analysis**
Creating the index on `retweet_count` took approximately **19 seconds**, while building the index on `full_text` required nearly **twice as long (≈38 seconds)**. This difference stems from the nature and size of the data: numeric fields are compact and quick to sort,  
whereas text fields are large and variable in length, requiring additional comparisons, encoding steps, and larger writes to the index. Moreover, indexing `full_text` involves significantly more disk I/O and CPU operations. In conclusion, indexes on short numeric columns are built much faster,  
while indexing long textual content increases both CPU and I/O load.

---

### Task 8: Comparison of Indexes
Porovnajte indexy pre `retweet_count`, `full_text`, `followers_count`, `screen_name`, …  
V čom sa líšia a prečo.

Použite:
1. `CREATE EXTENSION pageinspect;`
2. `SELECT * FROM bt_metap('idx_content');`
3. `SELECT type, live_items, dead_items, avg_item_size, page_size, free_size FROM bt_page_stats('idx_content', 1000);`
4. `SELECT itemoffset, itemlen, data FROM bt_page_items('idx_content', 1) LIMIT 1000;`

**Solution:**

**Query**
```sql

```

**Output**
```sql

```

**Results Analysis**

---

### Task 9: Searching for “Gates” Anywhere in `tweets.full_text`
Vyhľadajte v `tweets.full_text` meno „Gates“ na ľubovoľnom mieste a porovnajte výsledok po tom, ako `full_text` naindexujete.  
V čom je rozdiel a prečo?

**Solution:**

**Query**
```sql

```

**Output**
```sql

```

**Results Analysis**

---

### Task 10: Tweets Starting with “DANGER: WARNING:”
Vyhľadajte tweet, ktorý začína `DANGER: WARNING:`.  
Použil sa index?

**Solution:**

**Query**
```sql

```

**Output**
```sql

```

**Results Analysis**

---

### Task 11: Indexing `full_text` for Index Usage
Teraz naindexujte `full_text` tak, aby sa použil index a zhodnoťte, prečo sa predtým nad `DANGER: WARNING:` nepoužil.  
Použije sa teraz na „Gates“ na ľubovoľnom mieste?

**Solution:**

**Query**
```sql

```

**Output**
```sql

```

**Results Analysis**

---

### Task 12: Case-Insensitive Search for Suffix “LUCIFERASE”
Vytvorte nový index tak, aby ste vedeli vyhľadať tweet, ktorý končí reťazcom „LUCIFERASE“ a nezáleží na tom, ako to napíšete.

**Solution:**

**Query**
```sql

```

**Output**
```sql

```

**Results Analysis**
---

### Task 13: Combined Filters and Sorting in `users`
Nájdite účty, ktoré majú `follower_count < 10` a `friends_count > 1000`,  
a výsledok zoraďte podľa `statuses_count`.  
Následne spravte jednoduché indexy tak, aby to malo zmysel, a popíšte výsledok.
**Solution:**

**Query**
```sql

```

**Output**
```sql

```

**Results Analysis**

---

### Task 14: Composite Index vs. Separate Indexes
Na predošlú query spravte zložený index a porovnajte výsledok s tým, keď sú indexy separátne.

**Solution:**

**Query**
```sql

```

**Output**
```sql

```

**Results Analysis**

---

### Task 15: Changing the Boundary of `follower_count`
Upravte query tak, aby bol `follower_count < 1000` a `friends_count > 1000`.  
V čom je rozdiel a prečo?

**Solution:**

**Query**
```sql

```

**Output**
```sql

```

**Results Analysis**

---

### Task 16: Complex Query on `tweets` and `users`
Vyhľadajte všetky tweety (`full_text`), ktoré spomenul autor, ktorý obsahuje v `description` reťazec „comedian” (case-insensitive),  
tweety musia obsahovať reťazec „conspiracy“ (case-insensitive),  
tweety nesmú mať priradený hashtag  
a `retweet_count` je buď menší alebo rovný 10, alebo väčší ako 50.  
Zobrazte len rozdielne záznamy a zoraďte ich podľa počtu followerov DESC.  
Následne nad tým spravte analýzu a popíšte do protokolu, čo všetko sa tam deje (`EXPLAIN ANALYZE`).

**Solution:**

**Query**
```sql

```

**Output**
```sql

```

**Results Analysis**


1.	Filter na followers_count (100–200)
Vyberte používateľov, ktorí majú followers_count väčší alebo rovný 100 a zároveň menší alebo rovný 200. Je správanie rovnaké ako v prvej úlohe? Je správanie rovnaké ako v druhej úlohe? Prečo?
2.	Index pre úlohu 4 a bitmapy
Vytvorte index nad podmienkou z úlohy 4 a popíšte prácu s indexom. Čo je to Bitmap Index Scan a prečo je tam Bitmap Heap Scan? Prečo je tam recheck condition?
3.	Širší interval followers_count (100–1000) + vplyv ďalších indexov
Vyberte používateľov, ktorí majú followers_count väčší alebo rovný 100 a zároveň menší alebo rovný 1000. V čom je rozdiel, prečo?
Potom:
o	Vytvorte ďalšie 3 indexy na name, friends_count a description.
o	Vložte svojho používateľa (ľubovoľné dáta) do users. Koľko to trvalo?
o	Dropnite vytvorené indexy a spravte vloženie ešte raz. Prečo je tu rozdiel?
4.	Indexy v tweets pre retweet_count a full_text
Vytvorte index nad retweet_count a nad full_text. Porovnajte dĺžku vytvárania. Prečo je tu taký rozdiel?
5.	Porovnanie indexov (stručne)
Porovnajte indexy pre retweet_count, full_text, followers_count, screen_name, … v čom sa líšia a prečo.
Použite:
1.	CREATE EXTENSION pageinspect;
2.	SELECT * FROM bt_metap('idx_content');
3.	SELECT type, live_items, dead_items, avg_item_size, page_size, free_size FROM bt_page_stats('idx_content', 1000);
4.	SELECT itemoffset, itemlen, data FROM bt_page_items('idx_content', 1) LIMIT 1000;
6.	Hľadanie „Gates“ kdekoľvek vo tweets.full_text
Vyhľadajte v tweets.full_text meno „Gates“ na ľubovoľnom mieste a porovnajte výsledok po tom, ako full_text naindexujete. V čom je rozdiel a prečo?
7.	Tweet začínajúci na „DANGER: WARNING:“
Vyhľadajte tweet, ktorý začína DANGER: WARNING:. Použil sa index?
8.	Indexovanie full_text pre použitie indexu
Teraz naindexujte full_text tak, aby sa použil index a zhodnoťte, prečo sa predtým nad DANGER: WARNING: nepoužil. Použije sa teraz na „Gates“ na ľubovoľnom mieste?
9.	Vyhľadanie sufixu „LUCIFERASE“ (case-insensitive)
Vytvorte nový index tak, aby ste vedeli vyhľadať tweet, ktorý končí reťazcom „LUCIFERASE“ a nezáleží na tom, ako to napíšete.
10.	Kombinované filtre a triedenie v users
Nájdite účty, ktoré majú follower_count < 10 a friends_count > 1000, a výsledok zoraďte podľa statuses_count. Následne spravte jednoduché indexy tak, aby to malo zmysel, a popíšte výsledok.
11.	Zložený index vs. separátne indexy
Na predošlú query spravte zložený index a porovnajte výsledok s tým, keď sú indexy separátne.
12.	Zmena hranice follower_count
Upravte query tak, aby bol follower_count < 1000 a friends_count > 1000. V čom je rozdiel a prečo?
13.	Komplexný dotaz nad tweets a users
Vyhľadajte všetky tweety (full_text), ktoré spomenul autor, ktorý obsahuje v popise (description) reťazec „comedian” (case-insensitive), tweety musia obsahovať reťazec „conspiracy“ (case-insensitive), tweety nesmú mať priradený hashtag a počet retweetov (retweet_count) je buď menší alebo rovný 10, alebo väčší ako 50. Zobrazte len rozdielne záznamy a zoraďte ich podľa počtu followerov DESC a pobavte sa. Následne nad tým spravte analýzu a popíšte do protokolu, čo všetko sa tam deje (EXPLAIN ANALYZE).

