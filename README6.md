# Task 6
## Task 1

Kod nайprv MATCH nájde Trumpov účet podľa screen_name a pôvodný tweet podľa id, aby sa viazal na existujúce uzly. 
Potom MERGE (me:Account {screen_name:'myNewAccount'}) vytvorí alebo znovu použije tvoj účet a MERGE (me)-[:FOLLOWS]->(trump) zabezpečí, 
že ho práve raz sleduješ. Nakoniec MERGE (me)-[:POSTS]->(rt:Tweet)-[:RETWEETS]->(orig) vytvorí alebo znovu použije cestu, kde tvoj tweet rt retweetuje pôvodný Trumpov tweet, čím spĺňa požadovaný vzor.
​
```
MATCH (trump:Account {screen_name:'realDonaldTrump'})
MATCH (orig:Tweet {id:'1237027356314869761'})
MERGE (me:Account {screen_name:'myNewAccount'})
MERGE (me)-[:FOLLOWS]->(trump)
MERGE (me)-[:POSTS]->(rt:Tweet)-[:RETWEETS]->(orig)
RETURN me, rt, trump, orig;
```

Na grafe vidno, že myNewAccount má jednu hranu FOLLOWS na Trumpa, ale až päť rôznych uzlov myRetweet_..., ktoré vznikli z predchádzajúcich spustení s CREATE, preto je tam 5 vzťahov POSTS a 5 RETWEETS. 
To znamená, že účet tento istý Trumpov tweet retweetol viackrát, hoci na splnenie zadania by stačil jeden takýto retweet.
<img width="2461" height="1011" alt="image" src="https://github.com/user-attachments/assets/b8102a75-0217-4e95-86ca-e2b63b048e9f" />

## Task 2

Dotaz najprv nájde každého autora a jeho pôvodné tweety cez vzťah (:Account)-[:POSTS]->(:Tweet). Potom pre každý takýto tweet vyhľadá všetky retweet‑tweety, ktoré naň ukazujú cez (:Tweet)-[:RETWEETS]->(:Tweet), čiže identifikuje všetky retweety daného originálu. Následne spáruje každý retweet s účtom, ktorý ho postol ((:Account)-[:POSTS]->(retweet)), a pomocou count(DISTINCT retweeter) spočíta, koľko rôznych účtov retweetovalo tweety daného autora; zoradením podľa tohto počtu a LIMIT 10 dostaneme TOP super‑spreaders.

```
MATCH (author:Account)-[:POSTS]->(orig:Tweet)
MATCH (retweet:Tweet)-[:RETWEETS]->(orig)
MATCH (retweeter:Account)-[:POSTS]->(retweet)
WHERE author <> retweeter
WITH author, count(DISTINCT retweeter) AS retweeterCount
RETURN author.screen_name AS screen_name, retweeterCount
ORDER BY retweeterCount DESC
LIMIT 10;
```

Na obrazovke vidno tabuľku, kde napríklad dougmar_ má retweeterCount = 3224, čo znamená, že jeho tweety boli retweetované 3224 rôznymi účtami, takže výsledok presne zodpovedá definícii super‑spreaders.

```
screen_name,retweeterCount
dougmar_,3224
maddieevelasco,3056
slothanova,2867
DonaldJTrumpJr,2268
ewarren,1761
iSmashFizzle,1714
replouiegohmert,1612
CarlosLoret,1382
TechnicalGuruji,1364
Virrrperez1,1357
```

<img width="1318" height="1087" alt="image" src="https://github.com/user-attachments/assets/95dbd0fd-79f5-4962-8774-cfa58e99b572" />

## Task 3

Dotaz najprv nájde všetky dvojice (follower)-[:FOLLOWS]->(acc) a pre každý acc spočíta počet rôznych followerov, pričom ďalej púšťa len účty s aspoň 20 followermi. 
Následne pre tieto účty vyhľadá všetky ich tweety cez (:Account)-[:POSTS]->(:Tweet) a pomocou OPTIONAL MATCH (retweeter:Account)-[:RETWEETS]->(t) + podmienky retweeter IS NULL vyfiltruje len tweety, ktoré nemajú žiadny retweet. V časti WITH ... count(DISTINCT t) AS noReachTweets potom pre každý účet spočíta počet takýchto „bezdosahových“ tweetov, výsledok zoradí podľa noReachTweets a obmedzí na TOP 20.


```
MATCH (follower:Account)-[:FOLLOWS]->(acc:Account)
WITH acc, count(DISTINCT follower) AS followerCount
WHERE followerCount >= 20

MATCH (acc)-[:POSTS]->(t:Tweet)
OPTIONAL MATCH (retweeter:Account)-[:RETWEETS]->(t)
WHERE retweeter IS NULL

WITH acc, followerCount, count(DISTINCT t) AS noReachTweets
WHERE noReachTweets > 0
RETURN acc.screen_name AS screen_name,
       noReachTweets,
       followerCount
ORDER BY noReachTweets DESC
LIMIT 20;
```

```
screen_name,noReachTweets,followerCount
BloodDonorsIn,83,76
VTVcanal8,61,91
Reuters,46,2084
thehill,42,89
ABSCBNNews,41,100
inquirerdotnet,39,79
CaraotaDigital,37,74
CNN,35,1718
latimes,32,90
PartidoPSUV,29,79
PTI_News,29,82
rapplerdotcom,28,58
CNNEE,27,2004
ANI,26,54
nytimes,24,1810
ndtv,24,1366
cnnphilippines,23,85
gmanews,23,75
htTweets,23,101
ABC,22,1493
```
Na obrazovke vidno tabuľku, kde sú pre každé screen_name zobrazené práve tieto počty: noReachTweets ako počet tweetov bez retweetu a followerCount ako počet followerov, takže výstup zodpovedá presne požiadavke zadania.

<img width="1342" height="1086" alt="image" src="https://github.com/user-attachments/assets/06c2e636-1051-4d86-a4f4-bec550254250" />
