# Assigment 4.2 Elastic - vyhľadávanie a mapovanie

Zadanie je zamerané na overenie vedomostí z vyhľadávania a agregácií. Pre každé zadanie je nutné pridať vstupný JSON, prvý výsledok vyhľadávania a zhotnotenie pre každú úlohu.


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


-----------------------------
Úloha 2: "Algoritmus trendov" – Function Score a Boosting
Cieľ: Vytvoriť vlastný hodnotiaci (ranking) algoritmus, ktorý uprednostní vplyvný obsah pred jednoduchou textovou zhodou.
Scenár: Budujete feed "Top Tweets". Jednoduchá textová zhoda nestačí, pretože vracia staré, nepopulárne tweety. Musíte zoradiť tweety na základe kombinácie textovej relevancie a sociálneho vplyvu.
Požiadavky:
Základná Query: `multi_match` query hľadajúca výraz "urgent coronavirus" v poliach `full_text` (boost 2.0) a `user.description` (štandardná váha).
Function Score: Zabaľte query do `function_score` na úpravu `_score`.
Field Value Factor: Použite logaritmus `retweet_count` na zvýšenie skóre. (Populárne tweety budú vyššie, ale logaritmus zabráni tomu, aby virálny tweet s 1M retweetmi úplne "prebil" ostatné výsledky).
Decay Function (Gauss): Aplikujte funkciu poklesu na pole `created_at`. Tweety z posledných 7 dní majú mať plnú váhu, pričom váha rýchlo klesá pre tweety staršie ako 30 dní.
Boosting: Explicitne zvýšte (boost) skóre tweetom, kde je `user.verified` nastavené na `true`.
Výstup: Komplexná `function_score` query a teoretická analýza: Ak overený používateľ tweetuje "coronavirus" dnes s 0 retweetmi, oproti neoverenému používateľovi, ktorý to tweetoval pred rokom s 10 000 retweetmi, ktorá zložka vašej query zabráni tomu, aby starý tweet dominoval?


-----------------------------


Úloha 3: Objavovanie tém – Nested Queries a Inner Hits
Cieľ: Filtrovať tweety na základe špecifických kombinácií entít, ktoré existujú vo vnorených (nested) objektoch.
Scenár: Hľadáte "vplyvné siete". Potrebujete nájsť tweety, ktoré obsahujú zároveň špecifický hashtag a špecifickú zmienku používateľa (mention), ale musia to byť samostatné podmienky spracované správne v rámci vnorenej štruktúry dát.
Požiadavky:
Nested Query: Mapping definuje `entities.hashtags` a `entities.user_mentions` ako nested objekty.
Booleovská logika (vnútorná):
Vytvorte `bool` query vo vnútri cesty `nested`.
`SHOULD`: Tweet musí obsahovať text hashtagu "covid" alebo "virus".
`MUST`: Tweet musí spomínať používateľa (v `entities.user_mentions`) so `screen_name` "realdonaldtrump".
Inner Hits: Použite `inner_hits` na vrátenie *len* konkrétneho hashtagu alebo zmienky, ktorá vyvolala zhodu, nie len celého rodičovského dokumentu.
Výstup: JSON query. Opíšte prečo by štandardná `match` query na `entities.hashtags.text` (bez kľúčového slova `nested`) mohla vrátiť nesprávne výsledky alebo zlyhať pri identifikácii vzťahu medzi hashtagom a zmienkou.


-----------------------------


Úloha 4: Globálny analytický dashboard – Agregácie a Bucketing
Cieľ: Vygenerovať štatistický súhrn porovnávajúci správanie špecifickej skupiny používateľov voči globálnemu datasetu.
Scenár: Vytvárate dashboard na analýzu komunity "Slovakia" (na základe polohy používateľa) v porovnaní so zvyškom sveta.
Požiadavky:
Filter Aggregation (Bucket "Slovakia"):
Vytvorte filter agregáciu pre dokumenty, kde `user.location` obsahuje "Venezolano" alebo "Venezuela".
Date Histogram (Vnútorná agregácia):
Vo vnútri bucketu Slovakia vytvorte `date_histogram` nad poľom `created_at` s kalendárnym intervalom `1d` (1 deň).
Global Aggregation:
Vedľa bucketu Slovakia (ako súrodenca/sibling) pridajte `global` agregáciu.
V rámci globálneho rozsahu spustite rovnaký `date_histogram`, aby ste zobrazili celkový objem tweetov za deň v celom indexe.
Metric Aggregation:
V oboch histogramoch (Venezuela aj Global) vypočítajte priemerný počet retweetov (`avg` nad `retweet_count`).
Výstup: Agregačná JSON query. Študent musí poskytnúť krátky report analyzujúci výsledky: Je skupina používateľov "Slovakia" aktívnejšia alebo pasívnejšia (podľa priemeru retweetov) v porovnaní s globálnym priemerom v nájdených dňoch?
