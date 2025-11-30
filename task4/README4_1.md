
# FIIT PDT — Zadanie: Elasticsearch a Mapovanie Tweetov

## Cieľ úlohy
- Preukázať schopnosť pracovať s indexami v Elasticsearch.
- Vedieť čítať a interpretovať technickú dokumentáciu a vytvoriť mapovanie pre reálne dáta.
- Vyskúšať definovanie vlastných textových analyzátorov.
- Navrhnúť produkčne pripravené a striktne definované mapovanie pre komplexný JSON súbor.
- Aplikovať techniky textovej analýzy (stemming, n-gramy, shingles) na vhodné textové polia.

## Podklady
- Oficiálny dátový slovník objektu Tweet.
- Ukážkový JSON dokument obsahujúci tweet, retweet a quoted_status.

## Predispozícia
1. Spustite si tri inštancie Elasticsearch-u.

A three-node Elasticsearch cluster was deployed using **docker-compose**.  
Each node runs in a separate container and automatically joins the same cluster through the configured discovery settings.
After the cluster was launched, its health and node status were checked.  
The results confirmed that **all three nodes are active** and successfully participating in the cluster.
```
(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4> docker-compose up -d
time="2025-11-20T11:10:17+01:00" level=warning msg="C:\\Users\\sirad\\PycharmProjects\\PDT1\\task4\\docker-compose.yml: the attribute `version` is obsolete, it will be ignored, please remove it to avoid potential confusion"
[+] Running 13/3
 ✔ es01 Pulled                                                                                                                               107.8s 
 ✔ es03 Pulled                                                                                                                               107.8s 
 ✔ es02 Pulled                                                                                                                               107.8s 
[+] Running 4/4
 ✔ Network task4_esnet  Created                                                                                                                0.0s 
 ✔ Container es02       Started                                                                                                                0.6s 
 ✔ Container es03       Started                                                                                                                0.6s 
 ✔ Container es01       Started                                                                                                                0.7s 

(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4> curl.exe -X GET "http://localhost:9200/_cat/nodes?v"
ip         heap.percent ram.percent cpu load_1m load_5m load_15m node.role   master name
172.18.0.4           44          96   4    1.60    0.83     0.32 cdfhilmrstw *      es01
172.18.0.2           33          96   3    1.60    0.83     0.32 cdfhilmrstw -      es03
172.18.0.3           32          96   3    1.60    0.83     0.32 cdfhilmrstw -      es02
(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4>
```
2. Vytvorte index pre tweets s optimálnym počtom shardov a replík pre trojuzlový cluster.

An index named `tweets` was created with an **optimized number of primary shards and replicas** for a three-node environment. Elasticsearch confirmed that the index was successfully created.
```
(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4> curl.exe -X PUT "http://localhost:9200/tweets" -H "Content-Type: application/json" -d '{\"settings\": {\"number_of_shards\": 3, \"number_of_replicas\": 1}}'
{"acknowledged":true,"shards_acknowledged":true,"index":"tweets"}

(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4> curl.exe -X GET "http://localhost:9200/_cat/indices?v"
health status index  uuid                   pri rep docs.count docs.deleted store.size pri.store.size dataset.size
green  open   tweets K0rIo2DtS3q6zsg1YsEhsw   3   1          0            0      1.3kb           681b         681b
(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4>
```

3. Zdôvodnite výber počtu shardov a replík.

Since the cluster contains three physical nodes, allocating **one primary shard per node** is the most balanced configuration. This provides Uniform distribution of data, Balanced indexing and search load and Natural horizontal scalability without reallocation overhead  
Each primary shard has one replica, resulting in three replica shards distributed across different nodes. It gives us **High availability**: if one node fails, the cluster remains operational; **Faster search performance**: replicas can serve search queries; **Improved read load balancing**

---

# Časť 1: Vlastné analyzátory (v časti settings.analysis)

Je potrebné definovať tri vlastné analyzátory aj s potrebnými komponentmi.

## Analyzátor englado (pre bežný anglický text)
- Tokenizer: standard  
- Char filter: html_strip  
- Token filtre: english_possessive_stemmer, lowercase, english_stop, english_stemmer

## Analyzátor custom_ngram (pre vyhľadávanie po častiach slova – type-ahead)
- Tokenizer: standard  
- Char filter: html_strip  
- Filtre: lowercase, asciifolding a vlastný filter typu ngram s dĺžkou 3 až 6 znakov

## Analyzátor custom_shingles (pre frázové vyhľadávanie)
- Tokenizer: standard  
- Char filter: html_strip  
- Filtre: lowercase, asciifolding a vlastný filter typu shingle, ktorý spája tokeny bez medzier


To implement the custom analyzers required in the assignment, I created a `settings.json` file containing all analyzer definitions.  
Since Elasticsearch does not allow modifying analyzers on an existing index, I deleted the original `tweets` index and recreated it with the full analyzer configuration included.  
The file defines three analyzers: `englando`, `custom_ngram`, and `custom_shingles`, each using the standard tokenizer, HTML strip filter, and the required token filters.  
I also added two custom token filters, `filter_ngrams` and `filter_shingles`, as specified in the task.  
After creating the index, Elasticsearch confirmed that all analyzers and filters were successfully registered, and the configuration is now ready for use in mapping and data indexing.


```
(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4> curl.exe -X PUT "http://localhost:9200/tweets" -H "Content-Type: application/json" --data-binary "@settings.json"
{"acknowledged":true,"shards_acknowledged":true,"index":"tweets"}
(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4> curl.exe -X GET "http://localhost:9200/tweets/_settings?pretty"
{
  "tweets" : {
    "settings" : {
      "index" : {
        "max_ngram_diff" : "6",
        "routing" : {
          "allocation" : {
            "include" : {
              "_tier_preference" : "data_content"
            }
          }
        },
        "number_of_shards" : "3",
        "provided_name" : "tweets",
        "creation_date" : "1763635718351",
        "analysis" : {
          "filter" : {
            "english_stemmer" : {
              "type" : "stemmer",
              "language" : "english"
            },
            "filter_ngrams" : {
              "type" : "ngram",
              "min_gram" : "3",
              "max_gram" : "6"
            },
            "filter_shingles" : {
              "max_shingle_size" : "2",
              "min_shingle_size" : "2",
              "token_separator" : "",
              "type" : "shingle"
            },
            "english_stop" : {
              "type" : "stop",
              "stopwords" : "_english_"
            },
            "possessive_english_stemmer" : {
              "type" : "stemmer",
              "language" : "possessive_english"
            }
          },
          "analyzer" : {
            "englando" : {
              "filter" : [
                "possessive_english_stemmer",
                "lowercase",
                "english_stop",
                "english_stemmer"
              ],
              "char_filter" : [
                "html_strip"
              ],
              "type" : "custom",
              "tokenizer" : "standard"
            },
            "custom_ngram" : {
              "filter" : [
                "lowercase",
                "asciifolding",
                "filter_ngrams"
              ],
              "char_filter" : [
                "html_strip"
              ],
              "type" : "custom",
              "tokenizer" : "standard"
            },
            "custom_shingles" : {
              "filter" : [
                "lowercase",
                "asciifolding",
                "filter_shingles"
              ],
              "char_filter" : [
                "html_strip"
              ],
              "type" : "custom",
              "tokenizer" : "standard"
            }
          },
          "char_filter" : {
            "html_strip_cf" : {
              "type" : "html_strip"
            }
          }
        },
        "number_of_replicas" : "1",
        "uuid" : "8j9YLDuxTFOn61C7IA35zQ",
        "version" : {
          "created" : "8500008"
        }
      }
    }
  }
}
```

---

# Časť 2: Tvorba striktne definovaného mapovania (v časti mappings)

Na základe dokumentácie a ukážkového JSON vytvorte kompletné mapovanie.

Požiadavky:
- Mappings musia byť striktne definované (dynamic: strict).
- Je potrebné namapovať všetky polia, ktoré existujú v dokumentácii aj v JSON.
- Musia byť zahrnuté aj rekurzívne objekty retweeted_status a quoted_status.
- Pre polia, ktoré sa nemajú indexovať, použite index: false.
- Pre vnorené objekty s nepredvídateľnou štruktúrou použite dynamic: false.

# Aplikácia analyzátorov na polia

1. Všetok anglický text (napr. full_text, user.description) sa analizuje analyzátorom englado.
2. Pomocou multi-fields sa zachová aj pôvodný typ poľa.  
   Príklad: textové pole má verziu s analyzátorom englado, verziu so shingles a surovú keyword verziu.
3. Názvy miest, krajín a URL adresy majú mať pridelené mapovanie s analyzátorom custom_ngram.
4. Hashtagy (entities.hashtags.text) sa majú indexovať ako keyword, ale používa sa normalizer pre case-insensitive vyhľadávanie.

# Výber dátových typov
Zvoľte správne typy pre jednotlivé polia:
- text
- keyword
- integer, long
- boolean
- date (kompatibilný s formátom Twitter API)
- geo_point alebo geo_shape
- object
- nested

# Zdôvodnenie rozhodnutí
Je potrebné vysvetliť:
- Prečo a pre ktoré objekty bol zvolený typ nested.
- Prečo je dôležité definovať rekurzívnu štruktúru pre retweeted_status a aké by boli dôsledky pri jej vynechaní.
- Rozdiel v použití analyzátorov custom_ngram a custom_shingles na poli user.name, a kedy by sa mal použiť ktorý.

## 1. Why the **nested** type was used and where

The `nested` type is used on the fields:

- entities.hashtags  
- entities.symbols  
- entities.user_mentions  
- entities.urls  
- and the same fields inside retweeted_status.entities and quoted_status.entities

These fields are lists of objects, and each object has its own internal structure.

Why nested?

- Each item in the list is a separate entity.  
- With a normal `object` type, Elasticsearch could mix fields from different list items.  
- `nested` ensures that every item is indexed separately but still belongs to the same tweet.

Example of a problem without nested:

If we have:
- {screen_name: john, indices: [1,2]}
- {screen_name: anna, indices: [3,4]}

A query like screen_name = john AND indices = 3 could match incorrectly.  
`nested` prevents this.

Conclusion:  
The `nested` type is correctly used for list-of-object fields to maintain accurate matching.


## 2. Why the full recursive structure for retweeted_status and quoted_status is necessary

A tweet can contain:

- a full retweeted tweet (retweeted_status)  
- a full quoted tweet (quoted_status)  
- and those inner tweets can contain more nested data

So the structure is recursive.

Why must it be fully defined?

- With `dynamic: strict`, Elasticsearch needs every field defined in the mapping.  
  Otherwise, the JSON import fails with “unknown field”.
- `retweeted_status` and `quoted_status` are full tweets, not shortened versions.  
- Searching must work the same on:
  - full_text  
  - retweeted_status.full_text  
  - quoted_status.full_text  
- If any nested parts are missing in the mapping, the data will not be indexed and cannot be searched.

Conclusion:  
Nested tweet objects must have the same full structure as the root tweet; otherwise, imports and searches will fail.


## 3. Difference between custom_ngram and custom_shingles and how they apply to user.name

The field user.name is indexed in multiple ways:

- default analyzer (englando)  
- ngram version (custom_ngram)  
- shingle version (custom_shingles)  
- raw keyword version

### custom_ngram
Used for partial and prefix-like search.  
Works well for autocomplete.

Example for “London”:
- lo, lon, londo, london  
- on, ond, ndon  

Used when we want results even after typing only a few

--- 

# Časť 3: Import dát
Importujte ukážkový JSON dokument do vytvoreného indexu.

```
(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4> curl.exe -X DELETE "http://localhost:9200/tweets"                                             
{"acknowledged":true}
(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4> curl.exe -X PUT "http://localhost:9200/tweets" -H "Content-Type: application/json" -d "@mapping.json"
{"acknowledged":true,"shards_acknowledged":true,"index":"tweets"}
(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4> curl.exe -X POST "http://localhost:9200/tweets/_doc" -H "Content-Type: application/json" -d "@tweet_ex3.json"
{"_index":"tweets","_id":"rq-MopoBfyqumleD40i3","_version":1,"result":"created","_shards":{"total":2,"successful":2,"failed":0},"_seq_no":0,"_primary_term":1}

(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4> curl.exe -X GET "http://localhost:9200/tweets/_analyze" -H "Content-Type: application/json" -d "@analyze.json"
{"tokens":[{"token":"hello","start_offset":0,"end_offset":5,"type":"<ALPHANUM>","position":0},{"token":"world","start_offset":6,"end_offset":11,"type":"<ALPHANUM>","position":1}]}
(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4> curl.exe -X GET "http://localhost:9200/tweets/_analyze" -H "Content-Type: application/json" -d "@ngram.json"
{"tokens":[{"token":"lo","start_offset":0,"end_offset":2,"type":"word","position":0},{"token":"lon","start_offset":0,"end_offset":3,"type":"word","position":1},{"token":"lond","start_offset":0,"end_offset":4,"type":"word","position":2},{"token":"londo","start_offset":0,"end_offset":5,"type":"word","position":3},{"token":"london","start_offset":0,"end_offset":6,"type":"word","position":4},{"token":"on","start_offset":1,"end_offset":3,"type":"word","position":5},{"token":"ond","start_offset":1,"end_offset":4,"type":"word","position":6},{"token":"ondo","start_offset":1,"end_offset":5,"type":"word","position":7},{"token":"ondon","start_offset":1,"end_offset":6,"type":"word","position":8},{"token":"nd","start_offset":2,"end_offset":4,"type":"word","position":9},{"token":"ndo","start_offset":2,"end_offset":5,"type":"word","position":10},{"token":"ndon","start_offset":2,"end_offset":6,"type":"word","position":11},{"token":"do","start_offset":3,"end_offset":5,"type":"word","position":12},{"token":"don","start_offset":3,"end_offset":6,"type":"word","position":13},{"token":"on","start_offset":4,"end_offset":6,"type":"word","position":14}]}
(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4> curl.exe -X GET "http://localhost:9200/tweets/_analyze" -H "Content-Type: application/json" -d "@hashtag.json"
{"tokens":[{"token":"helloworld","start_offset":0,"end_offset":10,"type":"word","position":0}]}
(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4> curl.exe -X GET "http://localhost:9200/tweets/_analyze" -H "Content-Type: application/json" -d "@shingle.json"
{"tokens":[{"token":"hello world","start_offset":0,"end_offset":11,"type":"shingle","position":0},{"token":"hello world from","start_offset":0,"end_offset":16,"type":"shingle","position":0,"positionLength":2},{"token":"world from","start_offset":6,"end_offset":16,"type":"shingle","position":1},{"token":"world from chatgpt","start_offset":6,"end_offset":24,"type":"shingle","position":1,"positionLength":2},{"token":"from chatgpt","start_offset":12,"end_offset":24,"type":"shingle","position":2}]}
(.venv) PS C:\Users\sirad\PycharmProjects\PDT1\task4>

```

# Časť 4: Experimentovanie s indexom a nódami

1. Experimentujte s clusterom a zistite:
   - Koľko nód musí bežať na to, aby Elasticsearch dokázal pridávať, mazať a vyhľadávať dokumenty.
   - Či je možné nastaviť fungovanie len s jednou nódou.
   - Ako sa správa dostupnosť dokumentov pri výpadku nód.

## Výstup
### 1. Test of cluster availability with different numbers of running nodes

#### 1.1 Cluster state with all three nodes running
Command:
curl -X GET "http://localhost:9200/_cluster/health?pretty"

Output:
{
  "cluster_name": "my-es-cluster",
  "status": "green",
  "number_of_nodes": 3,
  "number_of_data_nodes": 3,
  "active_shards_percent_as_number": 100.0
}

Conclusion:  
The cluster is fully operational — reading, writing, and deleting documents all work correctly.


#### 1.2 Stopping one data node (es03)
Command:
docker stop es03  
curl -X GET "http://localhost:9200/_cluster/health?pretty"

Output:
{
  "cluster_name": "my-es-cluster",
  "status": "green",
  "number_of_nodes": 2,
  "number_of_data_nodes": 2,
  "active_shards_percent_as_number": 100.0
}

Conclusion:  
The cluster continues to function.  
Documents remain available, and write operations are allowed.


#### 1.3 Stopping the master node (es01)
Command:
docker stop es01  
curl -X GET "http://localhost:9200/_cluster/health?pretty"

Output:
{
  "error": { "type": "master_not_discovered_exception" },
  "status": 503
}

Conclusion:  
Without the master node, the cluster becomes non-functional.  
Indexing, deleting, and searching are no longer possible.


#### 1.4 Cluster state after two nodes stop

(The nodes restarted automatically after the master failure.)

Output:
{
  "status": "red",
  "number_of_nodes": 3,
  "active_primary_shards": 0,
  "unassigned_shards": 8
}

Conclusion:  
Primary shards cannot be assigned → the `tweets` index is unavailable.


#### 1.5 Recovery – restarting the nodes
Command:
docker start es01 es02 es03  
curl -X GET "http://localhost:9200/_cluster/health?pretty"

Output:
{
  "status": "green",
  "active_shards_percent_as_number": 100.0
}

Conclusion:  
The cluster automatically recovered and returned to full health.


### 2. Experiment with _seq_no and _primary_term

Purpose:
- update a document field (friends_count),
- observe changes in _seq_no and _primary_term,
- test how these values behave during node failures.


#### 2.1 Retrieving a document
Command:
curl -X GET "http://localhost:9200/tweets/_search?pretty"

Output (shortened):
{
  "_index": "tweets",
  "_id": "r6-vopoBfyqumleD90hW",
  "_seq_no": 0,
  "_primary_term": 1
}


#### 2.2 Updating the document using a script
Command:
curl -X POST "http://localhost:9200/tweets/_update/r6-vopoBfyqumleD90hW" \
-H "Content-Type: application/json" \
-d '{
  "script": {
    "source": "ctx._source.user.friends_count += params.inc",
    "params": { "inc": 1 }
  }
}'

Output:
{
  "_index": "tweets",
  "_id": "r6-vopoBfyqumleD90hW",
  "_version": 2,
  "_seq_no": 1,
  "_primary_term": 1
}

Conclusion:  
- _seq_no increased (0 → 1)  
- _primary_term stayed the same (1), because the primary shard did not fail.


#### 2.3 Stopping a data node (es02)
Command:
docker stop es02  
curl -X GET "http://localhost:9200/_cluster/health?pretty"

Output:
{
  "status": "yellow",
  "number_of_nodes": 2
}

Documents remain available.  
The primary shard is still active.


#### 2.4 Updating the document again
Output:
{
  "_seq_no": 2,
  "_primary_term": 1
}

Conclusion:  
- _seq_no increased again  
- _primary_term did not change, because the primary shard survived


#### 2.5 Stopping the master node (es01)
Command:
docker stop es01  
curl -X GET "http://localhost:9200/_cluster/health?pretty"

Output:
{
  "error": { "type": "master_not_discovered_exception" }
}

Conclusion:  
Document updates are no longer possible.


#### 2.6 After restarting the nodes
Command:
docker start es01 es02  
curl -X GET "http://localhost:9200/tweets/_search?pretty"

Output:
{
  "_seq_no": 2,
  "_primary_term": 2
}

Conclusion:  
- _primary_term increased (1 → 2),  
  because the primary shard was recovered or reassigned.

---

2. Upravte ľubovoľné pole (napr. tweets.friends_count) pomocou skriptu a sledujte:
   - zmeny hodnôt _seq_no
   - zmeny _primary_term
   pri vypínaní a zapínaní nód.

## Výstup
### 1. Determining how many nodes must run for the cluster to remain functional

#### Checking the cluster state with 3 nodes
Command:
curl -X GET "http://localhost:9200/_cluster/health?pretty"

Result:
- status: green  
- number_of_nodes: 3  

#### Stopping one data node
docker stop es03  
curl -X GET "http://localhost:9200/_cluster/health?pretty"

Result:
- status: yellow  
- number_of_nodes: 2  

Search and indexing operations still worked.

#### Stopping the master node (es01)
docker stop es01  
curl -X GET "http://localhost:9200/_cluster/health?pretty"

Result:
- master_not_discovered_exception  
- status: 503  

Conclusion:  
The cluster requires the master node to be running in order to add, delete, and search documents.  
Losing one data node does not stop the cluster, but losing the master does.

---

### 2. Is it possible to run Elasticsearch on a single node?

Yes, but only with the setting:
discovery.type: single-node

In the current 3-node cluster, stopping two nodes resulted in:

curl -X GET "http://localhost:9200/_cluster/health?pretty"

Result:
- status: red  
- active_primary_shards: 0  
- unassigned_shards: 8  

Conclusion:  
In the default configuration, a single node is not enough.  
Single-node mode is the only way to run Elasticsearch with one server.

---

### 3. Document availability during node failures

#### After stopping one data node (es03)
- cluster state: yellow  
- primary shards are active  
- documents are available  
- both read and write operations work  

#### After stopping two nodes including the master
- master_not_discovered_exception  
- status: red  
- no operations are possible  
- documents are unavailable  
- shards become unassigned  

#### After restarting all nodes
docker start es01 es02 es03  
Then checking the cluster:

curl -X GET "http://localhost:9200/_cluster/health?pretty"

Result:
- status: green  
- active_shards_percent_as_number: 100.0  

Conclusion:  
The cluster can tolerate the failure of one node, but not the majority of nodes or the master node.


### Final Conclusions

#### How many nodes must run?
Minimum:  
- 2 nodes (master + at least one data node)

With only 1 node, the cluster is non-functional unless using:
discovery.type: single-node

#### Is it possible to run Elasticsearch on one node?
Yes, but only in single-node mode.  
Otherwise, a single node is not enough.

#### How do documents behave during node failures?
- Loss of one data node: documents remain available  
- Loss of the master node: the entire cluster stops  
- After restart, shards are automatically reallocated

#### How do _seq_no and _primary_term change?
- _seq_no increments with every update  
- _primary_term changes only after a primary shard or master failure

P.S.
Since the web page didnt worked, I took the example of tweet structure from the Assigment1 and also the json example from one of the file. Thank you :)
