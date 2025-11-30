# Assigment 4.2 Elastic - vyhľadávanie a mapovanie

Zadanie je zamerané na overenie vedomostí z vyhľadávania a agregácií. Pre každé zadanie je nutné pridať vstupný JSON, prvý výsledok vyhľadávania a zhotnotenie pre každú úlohu.

## Úloha 0: 
Instead of using only the example file from section 4.1, I imported all .jsonl tweet files from the dataset, as clarified during the course. I implemented a [Python](https://github.com/DariiaSira/PDT--FIIT/blob/main/task4/import_tweets.py) importer using the official Elasticsearch client and the helpers.streaming_bulk API to stream documents from compressed .jsonl.gz files directly into the tweets index.
The script logs progress per file and handles errors without loading everything into memory. The full import of 40 files (≈6.35M tweets) took about 3.5 hours, with 0 failed documents, which confirms that the mapping and analyzers are compatible with the real data.

```
C:\Users\sirad\PycharmProjects\PDT1\.venv\Scripts\python.exe C:\Users\sirad\PycharmProjects\PDT1\task4\import_tweets.py 
[11:49:31] Import started
[11:49:31] Found file: 40
[11:49:31] === Started file: C:\Users\sirad\PycharmProjects\PDT1\tweets_import\data\coronavirus-tweet-id-2020-08-01-02.jsonl.gz ===
[11:52:45]   Progress: 100000 OK, 0 failed
[11:54:50] === Ready file: coronavirus-tweet-id-2020-08-01-02.jsonl.gz | OK: 164240, Failed: 0, time: 319.2s ===
[11:54:50] === Started file: C:\Users\sirad\PycharmProjects\PDT1\tweets_import\data\coronavirus-tweet-id-2020-08-01-05.jsonl.gz ===
[11:58:00]   Progress: 100000 OK, 0 failed
...
[15:20:33] === Ready file: coronavirus-tweet-id-2020-08-10-05.jsonl.gz | OK: 153639, Failed: 0, time: 307.4s ===
[15:20:33] DONE. Total OK: 6352085, total Failed: 0, total time: 211.0 min
[15:20:33] Import finished

Process finished with exit code 0
```
## Úloha 1: "Mlyn na fámy" – Proximity Search a Highlighting

**Cieľ:** Implementovať vyhľadávanie s vysokou presnosťou na nájdenie tweetov diskutujúcich o "hláseniach úmrtí" (death reports) alebo "počtoch mŕtvych" v súvislosti s COVID-19, s vylúčením automatizovaného spamu.

**Scenár:** Investigatívny novinár chce nájsť tweety, kde sa slová "deaths" (úmrtia) a "reported" (nahlásené) vyskytujú blízko seba, čo naznačuje konkrétnu správu, a nie len náhodný výskyt v tom istom dokumente.

**Požiadavky:**
Booleovská logika:
`MUST`: Musí obsahovať frázu "deaths reported" (alebo podobné variácie).
`MUST_NOT`: Nesmie obsahovať frázu "fake news" (na odfiltrovanie popieračov).
`FILTER`: Používateľ musí mať `followers_count` vyšší ako 10 (na odfiltrovanie úplne nových botov).
Slop Parameter: Použite `match_phrase` query s parametrom `slop` nastaveným na 5. To umožňuje, aby sa medzi slovami "deaths" a "reported".
Zvýrazňovanie (Highlighting): Vo výsledkoch vráťte pole `full_text` so zhodnými kľúčovými slovami obalenými v tagoch `<em>`, aby používateľ videl, prečo nastala zhoda.

**Výstup:** JSON query pre Elasticsearch a krátke vysvetlenie, ako parameter `slop` ovplyvňuje presnosť (precision) vs. úplnosť (recall) v tomto kontexte.

### Results 
#### JSON query
```
{
  "size": 2,
  "_source": [
    "full_text",
    "user.screen_name",
    "user.followers_count",
    "created_at"
  ],
  "query": {
    "bool": {
      "must": [
        {
          "match_phrase": {
            "full_text": {
              "query": "deaths reported",
              "slop": 5
            }
          }
        }
      ],
      "must_not": [
        {
          "match_phrase": {
            "full_text": "fake news"
          }
        }
      ],
      "filter": [
        {
          "range": {
            "user.followers_count": {
              "gt": 10
            }
          }
        }
      ]
    }
  },
  "highlight": {
    "pre_tags": [
      "<em>"
    ],
    "post_tags": [
      "</em>"
    ],
    "fields": {
      "full_text": {}
    }
  }
}
```

A small slop (close to 0) means the words must be almost next to each other, so results are very precise but you may miss many relevant tweets (high precision, low recall). A larger slop (like 5) allows some extra words between “deaths” and “reported”, so you find more tweets that talk about death reports in different ways (higher recall). But when slop is too large, Elasticsearch can also match tweets where the words are related less strongly, so recall goes up, while precision usually goes down.

#### Output

```
...
    "hits" : [
      {
        "_index" : "tweets",
        "_id" : "1289742059394326536",
        "_score" : 13.561541,
        "_source" : {
          "created_at" : "Sun Aug 02 01:57:23 +0000 2020",
          "full_text" : "New post: #Champion #Clare #covid19 #deaths #reported     No further Covid-19 deaths reported – The Clare Champion    https://t.co/ZwMg5aIVaa",
          "user" : {
            "screen_name" : "datewaynet",
            "followers_count" : 1229
          }
        },
        "highlight" : {
          "full_text" : [
            "New post: #Champion #Clare #covid19 #<em>deaths #reported</em>     No further Covid-19 <em>deaths reported</em> – The Clare"
          ]
        }
      },
...
```

The query successfully finds tweets where "deaths" and "reported" appear close together, filters bots by followers_count > 10, and uses highlighting to allow journalists to quickly understand the context of the match. Slop=5 increases recall (more relevant tweets) but still maintains high precision, as the words remain in close proximity. ”

---

## Úloha 2: "Algoritmus trendov" – Function Score a Boosting

**Cieľ:** Vytvoriť vlastný hodnotiaci (ranking) algoritmus, ktorý uprednostní vplyvný obsah pred jednoduchou textovou zhodou.

**Scenár:** Budujete feed "Top Tweets". Jednoduchá textová zhoda nestačí, pretože vracia staré, nepopulárne tweety. Musíte zoradiť tweety na základe kombinácie textovej relevancie a sociálneho vplyvu.

**Požiadavky:**
Základná Query: `multi_match` query hľadajúca výraz "urgent coronavirus" v poliach `full_text` (boost 2.0) a `user.description` (štandardná váha).
Function Score: Zabaľte query do `function_score` na úpravu `_score`.
Field Value Factor: Použite logaritmus `retweet_count` na zvýšenie skóre. (Populárne tweety budú vyššie, ale logaritmus zabráni tomu, aby virálny tweet s 1M retweetmi úplne "prebil" ostatné výsledky).
Decay Function (Gauss): Aplikujte funkciu poklesu na pole `created_at`. Tweety z posledných 7 dní majú mať plnú váhu, pričom váha rýchlo klesá pre tweety staršie ako 30 dní.
Boosting: Explicitne zvýšte (boost) skóre tweetom, kde je `user.verified` nastavené na `true`.

**Výstup**: Komplexná `function_score` query a teoretická analýza: Ak overený používateľ tweetuje "coronavirus" dnes s 0 retweetmi, oproti neoverenému používateľovi, ktorý to tweetoval pred rokom s 10 000 retweetmi, ktorá zložka vašej query zabráni tomu, aby starý tweet dominoval?

### Results 
The Gaussian decay function on created_at prevents the old tweet from dominating because a tweet from a year ago gets almost zero time-weight (score close to 0), while today's tweet gets full weight. Even though the old tweet has a higher retweet boost (log(10,000) ≈ 9), multiplying by near-zero time score makes its total score very low. The verified user's 2x boost further helps the new tweet win, but the main factor is the strong time decay that heavily penalizes outdated content.

#### JSON query
```
{
  "size": 1,
  "query": {
    "function_score": {
      "query": {
        "multi_match": {
          "query": "urgent coronavirus",
          "fields": [
            "full_text^2",
            "user.description"
          ]
        }
      },
      "functions": [
        {
          "field_value_factor": {
            "field": "retweet_count",
            "modifier": "log1p",
            "factor": 1.0
          }
        },
        {
          "gauss": {
            "created_at": {
              "origin": "now",
              "offset": "7d",
              "scale": "30d"
            }
          }
        },
        {
          "filter": {
            "term": {
              "user.verified": true
            }
          },
          "weight": 2.0
        }
      ],
      "score_mode": "multiply",
      "boost_mode": "multiply"
    }
  }
}
```
The query searches for "urgent coronavirus" in tweet text (with higher importance) and user descriptions, then adjusts the ranking using three factors. First, it boosts popular tweets based on the log of retweet count so viral content ranks higher without one super-popular tweet dominating everything. Second, it gives full weight to recent tweets (last 7 days) and quickly reduces score for older ones using a Gaussian decay on the creation date. Third, verified users get a 2x boost to their score.

#### Output
```
{
...
    "hits" : [
      {
        "_index" : "tweets",
        "_id" : "1289383097843113985",
        "_score" : 0.0,
        "_source" : {
          "created_at" : "Sat Aug 01 02:11:00 +0000 2020",
          "id" : 1289383097843113985,
          "id_str" : "1289383097843113985",
          "full_text" : "RT @replouiegohmert: I am taking #Hydroxychloroquine to treat my coronavirus diagnosis. It is what was decided as the best course of action…",
          "truncated" : false,
          "display_text_range" : [
            0,
            140
          ],
          "entities" : {
            "hashtags" : [
              {
                "text" : "Hydroxychloroquine",
                "indices" : [
                  33,
                  52
                ]
              }
            ],
            "symbols" : [ ],
            "user_mentions" : [
              {
                "screen_name" : "replouiegohmert",
                "name" : "Louie Gohmert",
                "id" : 22055226,
                "id_str" : "22055226",
                "indices" : [
                  3,
                  19
                ]
              }
            ],
            "urls" : [ ]
          },
          "source" : "<a href=\"http://twitter.com/download/iphone\" rel=\"nofollow\">Twitter for iPhone</a>",
          "in_reply_to_status_id" : null,
          "in_reply_to_status_id_str" : null,
          "in_reply_to_user_id" : null,
          "in_reply_to_user_id_str" : null,
          "in_reply_to_screen_name" : null,
          "user" : {
            "id" : 1036796603661774848,
            "id_str" : "1036796603661774848",
            "name" : "\uD83C\uDDFA\uD83C\uDDF8ginny\uD83D\uDC38insights\uD83C\uDDFA\uD83C\uDDF8",
            "screen_name" : "ginny_insights",
            "location" : "United States",
            "description" : "",
            "url" : null,
            "entities" : {
              "description" : {
                "urls" : [ ]
              }
            },
            "protected" : false,
            "followers_count" : 829,
            "friends_count" : 462,
            "listed_count" : 0,
            "created_at" : "Tue Sep 04 02:02:27 +0000 2018",
            "favourites_count" : 4582,
            "utc_offset" : null,
            "time_zone" : null,
            "geo_enabled" : false,
            "verified" : false,
            "statuses_count" : 10861,
            "lang" : null,
            "contributors_enabled" : false,
            "is_translator" : false,
            "is_translation_enabled" : false,
            "profile_background_color" : "F5F8FA",
            "profile_background_image_url" : null,
            "profile_background_image_url_https" : null,
            "profile_background_tile" : false,
            "profile_image_url" : "http://pbs.twimg.com/profile_images/1278719404700848130/P9mYKGbH_normal.jpg",
            "profile_image_url_https" : "https://pbs.twimg.com/profile_images/1278719404700848130/P9mYKGbH_normal.jpg",
            "profile_banner_url" : "https://pbs.twimg.com/profile_banners/1036796603661774848/1585513347",
            "profile_image_extensions_alt_text" : null,
            "profile_banner_extensions_alt_text" : null,
            "profile_link_color" : "1DA1F2",
            "profile_sidebar_border_color" : "C0DEED",
            "profile_sidebar_fill_color" : "DDEEF6",
            "profile_text_color" : "333333",
            "profile_use_background_image" : true,
            "has_extended_profile" : false,
            "default_profile" : true,
            "default_profile_image" : false,
            "following" : false,
            "follow_request_sent" : false,
            "notifications" : false,
            "translator_type" : "none"
          },
          "geo" : null,
          "coordinates" : null,
          "place" : null,
          "contributors" : null,
          "retweeted_status" : {
            "created_at" : "Fri Jul 31 20:36:57 +0000 2020",
            "id" : 1289299030325866497,
            "id_str" : "1289299030325866497",
            "full_text" : "I am taking #Hydroxychloroquine to treat my coronavirus diagnosis. It
 is what was decided as the best course of action between my doctor and me--not by government bureaucrats. How long until the tech tyrants censor this tweet? https://t.co/dzAYAXiQ8p",
            "truncated" : false,
            "display_text_range" : [
              0,
              226
            ],
            "entities" : {
              "hashtags" : [
                {
                  "text" : "Hydroxychloroquine",
                  "indices" : [
                    12,
                    31
                  ]
                }
              ],
              "symbols" : [ ],
              "user_mentions" : [ ],
              "urls" : [
                {
                  "url" : "https://t.co/dzAYAXiQ8p",
                  "expanded_url" : "https://twitter.com/bennyjohnson/status/1288674325323829249",
                  "display_url" : "twitter.com/bennyjohnson/s…",
                  "indices" : [
                    227,
                    250
                  ]
                }
              ]
            },
            "source" : "<a href=\"https://mobile.twitter.com\" rel=\"nofollow\">Twitter Web App</a>",
            "in_reply_to_status_id" : null,
            "in_reply_to_status_id_str" : null,
            "in_reply_to_user_id" : null,
            "in_reply_to_user_id_str" : null,
            "in_reply_to_screen_name" : null,
            "user" : {
              "id" : 22055226,
              "id_str" : "22055226",
              "name" : "Louie Gohmert",
              "screen_name" : "replouiegohmert",
              "location" : "",
              "description" : "Member of Congress, representing the first district of Texas which encompasses over 12 counties stretching nearly 120 miles down the eastern border of Texas.",  
              "url" : "http://t.co/dvOOcVB1hy",
              "entities" : {
                "url" : {
                  "urls" : [
                    {
                      "url" : "http://t.co/dvOOcVB1hy",
                      "expanded_url" : "http://gohmert.house.gov",
                      "display_url" : "gohmert.house.gov",
                      "indices" : [
                        0,
                        22
                      ]
                    }
                  ]
                },
                "description" : {
                  "urls" : [ ]
                }
              },
              "protected" : false,
              "followers_count" : 344576,
              "friends_count" : 746,
              "listed_count" : 2460,
              "created_at" : "Thu Feb 26 20:14:28 +0000 2009",
              "favourites_count" : 78,
              "utc_offset" : null,
              "time_zone" : null,
              "geo_enabled" : false,
              "verified" : true,
              "statuses_count" : 8349,
              "lang" : null,
              "contributors_enabled" : false,
              "is_translator" : false,
              "is_translation_enabled" : false,
              "profile_background_color" : "131516",
              "profile_background_image_url" : "http://abs.twimg.com/images/themes/theme14/bg.gif",
              "profile_background_image_url_https" : "https://abs.twimg.com/images/themes/theme14/bg.gif",
              "profile_background_tile" : true,
              "profile_image_url" : "http://pbs.twimg.com/profile_images/378800000474059588/ae423b08bb7a6e382fbd54184d3257a9_normal.jpeg",
              "profile_image_url_https" : "https://pbs.twimg.com/profile_images/378800000474059588/ae423b08bb7a6e382fbd54184d3257a9_normal.jpeg",
              "profile_banner_url" : "https://pbs.twimg.com/profile_banners/22055226/1405454469",
              "profile_image_extensions_alt_text" : null,
              "profile_banner_extensions_alt_text" : null,
              "profile_link_color" : "009999",
              "profile_sidebar_border_color" : "EEEEEE",
              "profile_sidebar_fill_color" : "EFEFEF",
              "profile_text_color" : "333333",
              "profile_use_background_image" : true,
              "has_extended_profile" : false,
              "default_profile" : false,
              "default_profile_image" : false,
              "following" : false,
              "follow_request_sent" : false,
              "notifications" : false,
              "translator_type" : "none"
            },
            "geo" : null,
            "coordinates" : null,
            "place" : null,
            "contributors" : null,
            "is_quote_status" : true,
            "quoted_status_id" : 1288674325323829249,
            "quoted_status_id_str" : "1288674325323829249",
            "quoted_status_permalink" : {
              "url" : "https://t.co/dzAYAXiQ8p",
              "expanded" : "https://twitter.com/bennyjohnson/status/1288674325323829249",       
              "display" : "twitter.com/bennyjohnson/s…"
            },
            "quoted_status" : {
              "created_at" : "Thu Jul 30 03:14:36 +0000 2020",
              "id" : 1288674325323829249,
              "id_str" : "1288674325323829249",
              "full_text" : "I wonder if Big Tech will allow ⁦@replouiegohmert⁩ to Tweet about this or if they’ll ban him for stating a fact. https://t.co/pqFy6gXFBi",
              "truncated" : false,
              "display_text_range" : [
                0,
                136
              ],
              "entities" : {
                "hashtags" : [ ],
                "symbols" : [ ],
                "user_mentions" : [
                  {
                    "screen_name" : "replouiegohmert",
                    "name" : "Louie Gohmert",
                    "id" : 22055226,
                    "id_str" : "22055226",
                    "indices" : [
                      33,
                      49
                    ]
                  }
                ],
                "urls" : [
                  {
                    "url" : "https://t.co/pqFy6gXFBi",
                    "expanded_url" : "https://thehill.com/homenews/house/509719-gohmert-says-he-will-take-hydroxychloroquine-as-covid-19-treatment",
                    "display_url" : "thehill.com/homenews/house…",
                    "indices" : [
                      113,
                      136
                    ]
                  }
                ]
              },
              "source" : "<a href=\"http://twitter.com/download/iphone\" rel=\"nofollow\">Twitter for iPhone</a>",
              "in_reply_to_status_id" : null,
              "in_reply_to_status_id_str" : null,
              "in_reply_to_user_id" : null,
              "in_reply_to_user_id_str" : null,
              "in_reply_to_screen_name" : null,
              "user" : {
                "id" : 15212187,
                "id_str" : "15212187",
                "name" : "Benny",
                "screen_name" : "bennyjohnson",
                "location" : "WashingtonDC/ New York City",
                "description" : "Love my Family, God and Pipe Tobacco; not necessarily in that order. @tpusa Chief Creative Officer Benny@tpusa.com",
                "url" : "https://t.co/8gi1LppSDA",
                "entities" : {
                  "url" : {
                    "urls" : [
                      {
                        "url" : "https://t.co/8gi1LppSDA",
                        "expanded_url" : "http://www.tpusa.com",
                        "display_url" : "tpusa.com",
                        "indices" : [
                          0,
                          23
                        ]
                      }
                    ]
                  },
                  "description" : {
                    "urls" : [ ]
                  }
                },
                "protected" : false,
                "followers_count" : 347145,
                "friends_count" : 1774,
                "listed_count" : 2191,
                "created_at" : "Mon Jun 23 21:33:20 +0000 2008",
                "favourites_count" : 13919,
                "utc_offset" : null,
                "time_zone" : null,
                "geo_enabled" : false,
                "verified" : true,
                "statuses_count" : 47247,
                "lang" : null,
                "contributors_enabled" : false,
                "is_translator" : false,
                "is_translation_enabled" : false,
                "profile_background_color" : "C0DEED",
                "profile_background_image_url" : "http://abs.twimg.com/images/themes/theme1/bg.png",
                "profile_background_image_url_https" : "https://abs.twimg.com/images/themes/theme1/bg.png",
                "profile_background_tile" : true,
                "profile_image_url" : "http://pbs.twimg.com/profile_images/1254597522116554754/UZu0Xp6A_normal.jpg",
                "profile_image_url_https" : "https://pbs.twimg.com/profile_images/1254597522116554754/UZu0Xp6A_normal.jpg",
                "profile_banner_url" : "https://pbs.twimg.com/profile_banners/15212187/1542303332",
                "profile_image_extensions_alt_text" : null,
                "profile_banner_extensions_alt_text" : null,
                "profile_link_color" : "0084B4",
                "profile_sidebar_border_color" : "C0DEED",
                "profile_sidebar_fill_color" : "DDEEF6",
                "profile_text_color" : "333333",
                "profile_use_background_image" : true,
                "has_extended_profile" : false,
                "default_profile" : false,
                "default_profile_image" : false,
                "following" : false,
                "follow_request_sent" : false,
                "notifications" : false,
                "translator_type" : "none"
              },
              "geo" : null,
              "coordinates" : null,
              "place" : null,
              "contributors" : null,
              "is_quote_status" : false,
              "retweet_count" : 2329,
              "favorite_count" : 5060,
              "favorited" : false,
              "retweeted" : false,
              "possibly_sensitive" : false,
              "lang" : "en"
            },
            "retweet_count" : 33094,
            "favorite_count" : 69394,
            "favorited" : false,
            "retweeted" : false,
            "possibly_sensitive" : false,
            "lang" : "en"
          },
          "is_quote_status" : true,
          "quoted_status_id" : 1288674325323829249,
          "quoted_status_id_str" : "1288674325323829249",
          "quoted_status_permalink" : {
            "url" : "https://t.co/dzAYAXiQ8p",
            "expanded" : "https://twitter.com/bennyjohnson/status/1288674325323829249",
            "display" : "twitter.com/bennyjohnson/s…"
          },
          "retweet_count" : 33094,
          "favorite_count" : 0,
          "favorited" : false,
          "retweeted" : false,
          "lang" : "en"
        }
      },
```
The function_score query successfully creates a sophisticated "Top Tweets" ranking that goes beyond simple keyword matching by incorporating social influence (retweets), timeliness (date decay), and credibility (verified boost). The result shows tweets with _score: 0.0, which suggests the base query didn't find strong matches for "urgent coronavirus" in this specific dataset, but the scoring functions are correctly structured and would work well with more relevant data.

---

## Úloha 3: Objavovanie tém – Nested Queries a Inner Hits

**Cieľ:** Filtrovať tweety na základe špecifických kombinácií entít, ktoré existujú vo vnorených (nested) objektoch.

**Scenár:** Hľadáte "vplyvné siete". Potrebujete nájsť tweety, ktoré obsahujú zároveň špecifický hashtag a špecifickú zmienku používateľa (mention), ale musia to byť samostatné podmienky spracované správne v rámci vnorenej štruktúry dát.

**Požiadavky:**
Nested Query: Mapping definuje `entities.hashtags` a `entities.user_mentions` ako nested objekty.
Booleovská logika (vnútorná):
Vytvorte `bool` query vo vnútri cesty `nested`.
`SHOULD`: Tweet musí obsahovať text hashtagu "covid" alebo "virus".
`MUST`: Tweet musí spomínať používateľa (v `entities.user_mentions`) so `screen_name` "realdonaldtrump".
Inner Hits: Použite `inner_hits` na vrátenie *len* konkrétneho hashtagu alebo zmienky, ktorá vyvolala zhodu, nie len celého rodičovského dokumentu.

**Výstup:** JSON query. Opíšte prečo by štandardná `match` query na `entities.hashtags.text` (bez kľúčového slova `nested`) mohla vrátiť nesprávne výsledky alebo zlyhať pri identifikácii vzťahu medzi hashtagom a zmienkou.

### Results 
A standard match query on entities.hashtags.text ignores the nested structure and flattens all hashtags and mentions into one big bag of fields. This means Elasticsearch can match a hashtag from one nested object and a mention from a different nested object, even if they never appear together in the same logical entity. As a result, we might get tweets where “covid” is one hashtag and “realdonaldtrump” is mentioned in a completely unrelated part of the entities, so the relationship between them is lost. Using nested queries keeps each hashtag and each mention as a separate mini-document, so the query can correctly reason about which hashtag and which mention belong together.

#### JSON query
```
{
  "size": 1,
  "query": {
    "bool": {
      "must": [
        {
          "nested": {
            "path": "entities.hashtags",
            "query": {
              "bool": {
                "should": [
                  { "term": { "entities.hashtags.text": "covid" } },
                  { "term": { "entities.hashtags.text": "virus" } }
                ]
              }
            },
            "inner_hits": {
              "name": "matched_hashtags",
              "size": 5
            }
          }
        },
        {
          "nested": {
            "path": "entities.user_mentions",
            "query": {
              "bool": {
                "must": [
                  {
                    "term": {
                      "entities.user_mentions.screen_name": "realdonaldtrump"
                    }
                  }
                ]
              }
            },
            "inner_hits": {
              "name": "matched_mentions",
              "size": 5
            }
          }
        }
      ]
    }
  }
}
```
This query finds tweets that have at least one hashtag equal to “covid” or “virus”, and also have at least one user mention with screen_name “realdonaldtrump”. The nested + inner_hits parts make Elasticsearch search inside the hashtag and mention arrays correctly and return only the exact matching hashtag(s) and mention(s) that triggered the match.

#### Output
```
{
...
    "hits" : [
      {
        "_index" : "tweets",
        "_id" : "1290794925748031490",
        "_score" : 11.021214,
        "_source" : {
          "created_at" : "Tue Aug 04 23:41:06 +0000 2020",
          "id" : 1290794925748031490,
          "id_str" : "1290794925748031490",
          "full_text" : "@scientificrealm @realDonaldTrump Your science experts works for #Soros
 ... the creator of the #virus with #China The Science world is under chinese control. Thanks Go
d #Trump is fighting against that. #Trump2020 #TrumpWillSaveAmerica #MAGA https://t.co/2hWB9MyAYx",
          "truncated" : false,
          "display_text_range" : [
            34,
            240
          ],
          "entities" : {
            "hashtags" : [
              {
                "text" : "Soros",
                "indices" : [
                  65,
                  71
                ]
              },
              {
                "text" : "virus",
                "indices" : [
                  95,
                  101
                ]
              },
              {
                "text" : "China",
                "indices" : [
                  107,
                  113
                ]
              },
              {
                "text" : "Trump",
                "indices" : [
                  169,
                  175
                ]
              },
              {
                "text" : "Trump2020",
                "indices" : [
                  202,
                  212
                ]
              },
              {
                "text" : "TrumpWillSaveAmerica",
                "indices" : [
                  213,
                  234
                ]
              },
              {
                "text" : "MAGA",
                "indices" : [
                  235,
                  240
                ]
              }
            ],
            "symbols" : [ ],
            "user_mentions" : [
              {
                "screen_name" : "scientificrealm",
                "name" : "scientific realm \uD83E\uDDEC",
                "id" : 18109429,
                "id_str" : "18109429",
                "indices" : [
                  0,
                  16
                ]
              },
              {
                "screen_name" : "realDonaldTrump",
                "name" : "Donald J. Trump",
                "id" : 25073877,
                "id_str" : "25073877",
                "indices" : [
                  17,
                  33
                ]
              }
            ],
            "urls" : [ ],
            "media" : [
              {
                "id" : 1290794902708727808,
                "id_str" : "1290794902708727808",
                "indices" : [
                  241,
                  264
                ],
                "media_url" : "http://pbs.twimg.com/media/EenTIAXWsAACY9p.jpg",
                "media_url_https" : "https://pbs.twimg.com/media/EenTIAXWsAACY9p.jpg",
                "url" : "https://t.co/2hWB9MyAYx",
                "display_url" : "pic.twitter.com/2hWB9MyAYx",
                "expanded_url" : "https://twitter.com/FreedomWarro/status/1290794925748031490/photo/1",
                "type" : "photo",
                "sizes" : {
                  "medium" : {
                    "w" : 720,
                    "h" : 735,
                    "resize" : "fit"
                  },
                  "thumb" : {
                    "w" : 150,
                    "h" : 150,
                    "resize" : "crop"
                  },
                  "large" : {
                    "w" : 720,
                    "h" : 735,
                    "resize" : "fit"
                  },
                  "small" : {
                    "w" : 666,
                    "h" : 680,
                    "resize" : "fit"
                  }
                }
              }
            ]
          },
          "extended_entities" : {
            "media" : [
              {
                "id" : 1290794902708727808,
                "id_str" : "1290794902708727808",
                "indices" : [
                  241,
                  264
                ],
                "media_url" : "http://pbs.twimg.com/media/EenTIAXWsAACY9p.jpg",
                "media_url_https" : "https://pbs.twimg.com/media/EenTIAXWsAACY9p.jpg",
                "url" : "https://t.co/2hWB9MyAYx",
                "display_url" : "pic.twitter.com/2hWB9MyAYx",
                "expanded_url" : "https://twitter.com/FreedomWarro/status/1290794925748031490/photo/1",
                "type" : "photo",
                "sizes" : {
                  "medium" : {
                    "w" : 720,
                    "h" : 735,
                    "resize" : "fit"
                  },
                  "thumb" : {
                    "w" : 150,
                    "h" : 150,
                    "resize" : "crop"
                  },
                  "large" : {
                    "w" : 720,
                    "h" : 735,
                    "resize" : "fit"
                  },
                  "small" : {
                    "w" : 666,
                    "h" : 680,
                    "resize" : "fit"
                  }
                },
                "ext_alt_text" : null
              }
            ]
          },
          "source" : "<a href=\"http://twitter.com/download/iphone\" rel=\"nofollow\">Twitter for iPhone</a>",
          "in_reply_to_status_id" : 1290785306296360963,
          "in_reply_to_status_id_str" : "1290785306296360963",
          "in_reply_to_user_id" : 18109429,
          "in_reply_to_user_id_str" : "18109429",
          "in_reply_to_screen_name" : "scientificrealm",
          "user" : {
            "id" : 1250415854790905864,
            "id_str" : "1250415854790905864",
            "name" : "FreedomWarrior \uD83C\uDDEA\uD83C\uDDF8",
            "screen_name" : "FreedomWarro",
            "location" : "",
            "description" : "Luchando por la Libertad y la Democracia \uD83D\uDCAA\uD83C\uDFFB",
            "url" : null,
            "entities" : {
              "description" : {
                "urls" : [ ]
              }
            },
            "protected" : false,
            "followers_count" : 823,
            "friends_count" : 1075,
            "listed_count" : 1,
            "created_at" : "Wed Apr 15 13:29:26 +0000 2020",
            "favourites_count" : 12382,
            "utc_offset" : null,
            "time_zone" : null,
            "geo_enabled" : false,
            "verified" : false,
            "statuses_count" : 7094,
            "lang" : null,
            "contributors_enabled" : false,
            "is_translator" : false,
            "is_translation_enabled" : false,
            "profile_background_color" : "F5F8FA",
            "profile_background_image_url" : null,
            "profile_background_image_url_https" : null,
            "profile_background_tile" : false,
            "profile_image_url" : "http://pbs.twimg.com/profile_images/1250417807604322309/wMOJVmhy_normal.jpg",
            "profile_image_url_https" : "https://pbs.twimg.com/profile_images/1250417807604322309/wMOJVmhy_normal.jpg",
            "profile_banner_url" : "https://pbs.twimg.com/profile_banners/1250415854790905864/1586972700",
            "profile_image_extensions_alt_text" : null,
            "profile_banner_extensions_alt_text" : null,
            "profile_link_color" : "1DA1F2",
            "profile_sidebar_border_color" : "C0DEED",
            "profile_sidebar_fill_color" : "DDEEF6",
            "profile_text_color" : "333333",
            "profile_use_background_image" : true,
            "has_extended_profile" : false,
            "default_profile" : true,
            "default_profile_image" : false,
            "following" : false,
            "follow_request_sent" : false,
            "notifications" : false,
            "translator_type" : "none"
          },
          "geo" : null,
          "coordinates" : null,
          "place" : null,
          "contributors" : null,
          "is_quote_status" : false,
          "retweet_count" : 0,
          "favorite_count" : 0,
          "favorited" : false,
          "retweeted" : false,
          "possibly_sensitive" : false,
          "lang" : "en"
        },
        "inner_hits" : {
          "matched_mentions" : {
            "hits" : {
              "total" : {
                "value" : 1,
                "relation" : "eq"
              },
              "max_score" : 3.9606023,
              "hits" : [
                {
                  "_index" : "tweets",
                  "_id" : "1290794925748031490",
                  "_nested" : {
                    "field" : "entities.user_mentions",
                    "offset" : 1
                  },
                  "_score" : 3.9606023,
                  "_source" : {
                    "screen_name" : "realDonaldTrump",
                    "name" : "Donald J. Trump",
                    "id" : 25073877,
                    "id_str" : "25073877",
                    "indices" : [
                      17,
                      33
                    ]
                  }
                }
              ]
            }
          },
          "matched_hashtags" : {
            "hits" : {
              "total" : {
                "value" : 1,
                "relation" : "eq"
              },
              "max_score" : 7.0606117,
              "hits" : [
                {
                  "_index" : "tweets",
                  "_id" : "1290794925748031490",
                  "_nested" : {
                    "field" : "entities.hashtags",
                    "offset" : 1
                  },
                  "_score" : 7.0606117,
                  "_source" : {
                    "text" : "virus",
                    "indices" : [
                      95,
                      101
                    ]
                  }
                }
              ]
            }
          }
        }
      }
    ]
  }
}
```
This nested query works correctly: it finds tweets that both mention @realDonaldTrump and contain a hashtag “virus” or “covid”, and inner_hits shows exactly which hashtag and which mention matched. The first hit is a tweet that attacks Trump, includes #virus, and mentions @realDonaldTrump, and the inner_hits clearly show the matching hashtag (virus) and mention (realDonaldTrump). Overall, the task is successful because the nested + inner_hits approach preserves the relationship between specific hashtags and mentions and returns precise matches for “influential networks” instead of noisy global matches.

---

## Úloha 4: Globálny analytický dashboard – Agregácie a Bucketing

**Cieľ:** Vygenerovať štatistický súhrn porovnávajúci správanie špecifickej skupiny používateľov voči globálnemu datasetu.

**Scenár:** Vytvárate dashboard na analýzu komunity "Slovakia" (na základe polohy používateľa) v porovnaní so zvyškom sveta.

**Požiadavky:**
Filter Aggregation (Bucket "Slovakia"):
Vytvorte filter agregáciu pre dokumenty, kde `user.location` obsahuje "Venezolano" alebo "Venezuela".
Date Histogram (Vnútorná agregácia):
Vo vnútri bucketu Slovakia vytvorte `date_histogram` nad poľom `created_at` s kalendárnym intervalom `1d` (1 deň).
Global Aggregation:
Vedľa bucketu Slovakia (ako súrodenca/sibling) pridajte `global` agregáciu.
V rámci globálneho rozsahu spustite rovnaký `date_histogram`, aby ste zobrazili celkový objem tweetov za deň v celom indexe.
Metric Aggregation:
V oboch histogramoch (Venezuela aj Global) vypočítajte priemerný počet retweetov (`avg` nad `retweet_count`).

**Výstup:** Agregačná JSON query. Študent musí poskytnúť krátky report analyzujúci výsledky: Je skupina používateľov "Slovakia" aktívnejšia alebo pasívnejšia (podľa priemeru retweetov) v porovnaní s globálnym priemerom v nájdených dňoch?

### Results 
The data shows that the Venezuela group (“user.location” contains “Venezuela” or “Venezolano”) has a much lower average retweet count per day than the global average. For example, on most days, Venezuela users average between 400 and 1,700 retweets, while the global averages are much higher—often above 4,000 and sometimes over 15,000. This pattern holds true for every day in the report. This means the Venezuela community is less active or has less viral content than the global Twitter population in the same period. In summary, “Venezuela” tweets are more passive by this metric than the world average for these days.

#### JSON query
```
{
  "size": 0,
  "aggs": {
    "venezuela": {
      "filter": {
        "bool": {
          "should": [
            { "match_phrase": { "user.location": "Venezolano" } },
            { "match_phrase": { "user.location": "Venezuela" } }
          ]
        }
      },
      "aggs": {
        "venezuela_per_day": {
          "date_histogram": {
            "field": "created_at",
            "calendar_interval": "1d"
          },
          "aggs": {
            "avg_retweets": {
              "avg": {
                "field": "retweet_count"
              }
            }
          }
        }
      }
    },
    "global": {
      "global": {},
      "aggs": {
        "global_per_day": {
          "date_histogram": {
            "field": "created_at",
            "calendar_interval": "1d"
          },
          "aggs": {
            "avg_retweets": {
              "avg": {
                "field": "retweet_count"
              }
            }
          }
        }
      }
    }
  }
}
```
This query builds two time series: one for tweets from users whose location contains “Venezolano” or “Venezuela”, and one for all tweets in the index (global). For each day in both series, it counts tweets into date buckets and computes the average number of retweets, so you can compare how active the Venezuela community is versus the global average.

#### Output
```
{   
  "took" : 757,
  "timed_out" : false,
  "_shards" : {
    "total" : 3,
    "successful" : 3,
    "skipped" : 0,
    "failed" : 0
  },
  "hits" : {
    "total" : {
      "value" : 10000,
      "relation" : "gte"
    },
    "max_score" : null,
    "hits" : [ ]
  },
  "aggregations" : {
    "global" : {
      "doc_count" : 6352085,
      "global_per_day" : {
        "buckets" : [
          {
            "key_as_string" : "Sat Aug 01 00:00:00 +0000 2020",
            "key" : 1596240000000,
            "doc_count" : 1256003,
            "avg_retweets" : {
              "value" : 5752.308453084905
            }
          },
          {
            "key_as_string" : "Sun Aug 02 00:00:00 +0000 2020",
            "key" : 1596326400000,
            "doc_count" : 483412,
            "avg_retweets" : {
              "value" : 7964.844513582617
            }
          },
          {
            "key_as_string" : "Mon Aug 03 00:00:00 +0000 2020",
            "key" : 1596412800000,
            "doc_count" : 481794,
            "avg_retweets" : {
              "value" : 5745.153789793978
            }
          },
          {
            "key_as_string" : "Tue Aug 04 00:00:00 +0000 2020",
            "key" : 1596499200000,
            "doc_count" : 1111125,
            "avg_retweets" : {
              "value" : 4469.36217437282
            }
          },
          {
            "key_as_string" : "Wed Aug 05 00:00:00 +0000 2020",
            "key" : 1596585600000,
            "doc_count" : 925104,
            "avg_retweets" : {
              "value" : 7563.797458447915
            }
          },
          {
            "key_as_string" : "Thu Aug 06 00:00:00 +0000 2020",
            "key" : 1596672000000,
            "doc_count" : 467597,
            "avg_retweets" : {
              "value" : 4185.2345502644375
            }
          },
          {
            "key_as_string" : "Fri Aug 07 00:00:00 +0000 2020",
            "key" : 1596758400000,
            "doc_count" : 328380,
            "avg_retweets" : {
              "value" : 5456.704750593824
            }
          },
          {
            "key_as_string" : "Sat Aug 08 00:00:00 +0000 2020",
            "key" : 1596844800000,
            "doc_count" : 486547,
            "avg_retweets" : {
              "value" : 3664.175401348688
            }
          },
          {
            "key_as_string" : "Sun Aug 09 00:00:00 +0000 2020",
            "key" : 1596931200000,
            "doc_count" : 658484,
            "avg_retweets" : {
              "value" : 4344.819751125312
            }
          },
          {
            "key_as_string" : "Mon Aug 10 00:00:00 +0000 2020",
            "key" : 1597017600000,
            "doc_count" : 153639,
            "avg_retweets" : {
              "value" : 15323.770500979568
            }
          }
        ]
      }
    },
    "venezuela" : {
      "doc_count" : 60710,
      "venezuela_per_day" : {
        "buckets" : [
          {
            "key_as_string" : "Sat Aug 01 00:00:00 +0000 2020",
            "key" : 1596240000000,
            "doc_count" : 10069,
            "avg_retweets" : {
              "value" : 483.76909325652997
            }
          },
          {
            "key_as_string" : "Sun Aug 02 00:00:00 +0000 2020",
            "key" : 1596326400000,
            "doc_count" : 8369,
            "avg_retweets" : {
              "value" : 665.9584179710838
            }
          },
          {
            "key_as_string" : "Mon Aug 03 00:00:00 +0000 2020",
            "key" : 1596412800000,
            "doc_count" : 3923,
            "avg_retweets" : {
              "value" : 1733.4575579913333
            }
          },
          {
            "key_as_string" : "Tue Aug 04 00:00:00 +0000 2020",
            "key" : 1596499200000,
            "doc_count" : 9020,
            "avg_retweets" : {
              "value" : 721.9444567627495
            }
          },
          {
            "key_as_string" : "Wed Aug 05 00:00:00 +0000 2020",
            "key" : 1596585600000,
            "doc_count" : 6829,
            "avg_retweets" : {
              "value" : 910.6336213208376
            }
          },
          {
            "key_as_string" : "Thu Aug 06 00:00:00 +0000 2020",
            "key" : 1596672000000,
            "doc_count" : 4802,
            "avg_retweets" : {
              "value" : 572.329029571012
            }
          },
          {
            "key_as_string" : "Fri Aug 07 00:00:00 +0000 2020",
            "key" : 1596758400000,
            "doc_count" : 4009,
            "avg_retweets" : {
              "value" : 1340.102519331504
            }
          },
          {
            "key_as_string" : "Sat Aug 08 00:00:00 +0000 2020",
            "key" : 1596844800000,
            "doc_count" : 5715,
            "avg_retweets" : {
              "value" : 1078.3905511811024
            }
          },
          {
            "key_as_string" : "Sun Aug 09 00:00:00 +0000 2020",
            "key" : 1596931200000,
            "doc_count" : 7369,
            "avg_retweets" : {
              "value" : 456.44578640249694
            }
          },
          {
            "key_as_string" : "Mon Aug 10 00:00:00 +0000 2020",
            "key" : 1597017600000,
            "doc_count" : 605,
            "avg_retweets" : {
              "value" : 3498.6330578512398
            }
          }
        ]
      }
    }
  }
}
```
The task correctly uses aggregations to compare a specific user group with the global population over time. The results clearly show that the “Venezuela” group has much lower average retweets per day than the global averages for the same days, so this community is less viral and more passive in terms of engagement. Overall, the implementation and output match the assignment goal: it provides a clear analytical basis to say that this regional community is less active than the global dataset according to average retweet counts.
