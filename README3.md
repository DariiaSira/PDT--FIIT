# 🧭 Protokol z cvičenia – OpenStreetMap & Priestorové dáta (PostGIS / QGIS)

## 🧑‍🎓 Študent
**Meno a priezvisko:** _................................................_  
**Dátum odovzdania:** _................................................_  
**Predmet:** Priestorové databázové technológie  
**Cvičenie:** Práca s OSM dátami, PostGIS, QGIS  
**Semester:** ZS / 2025  

---

## 🧩 Zadanie

### 1. Stiahnite a importujte dataset pre **OpenStreetMap** z [https://download.geofabrik.de/europe/slovakia.html](https://download.geofabrik.de/europe/slovakia.html) do **novej databázy**.

I downloaded the OSM dataset for Slovakia from [Geofabrik](https://download.geofabrik.de/europe/slovakia.html) and created a new database called `osm_slovakia`.  
Then I enabled the **PostGIS** extension to work with spatial data.  
```
postgres=# CREATE DATABASE osm_slovakia;
osm_slovakia=# CREATE EXTENSION postgis;
CREATE EXTENSION
```

After that, I ran my Python script to import all shapefiles into PostgreSQL.  
As a result, I got **19 spatial tables**, for example: `gis_osm_roads_free_1`, `gis_osm_buildings_a_free_1`, etc.

```
import geopandas as gpd
from sqlalchemy import create_engine
import os

engine = create_engine("postgresql+psycopg2://postgres:postgres@localhost:5432/osm_slovakia")

data_dir = r"C:\Users\sirad\PycharmProjects\PDT1\slovakia-251027-free.shp"  

for file in os.listdir(data_dir):
    if file.endswith(".shp"):
        path = os.path.join(data_dir, file)
        name = os.path.splitext(file)[0]
        print(f"📥 Importujem {name} ...")

        gdf = gpd.read_file(path)
        if gdf.crs is None:
            gdf.set_crs(epsg=4326, inplace=True)
        gdf.to_postgis(name, engine, if_exists="replace", index=False)
```
and as result:
```
osm_slovakia=# \dt
                     List of tables
 Schema |            Name            | Type  |  Owner
--------+----------------------------+-------+----------
 public | gis_osm_buildings_a_free_1 | table | postgres
 public | gis_osm_landuse_a_free_1   | table | postgres
 public | gis_osm_natural_a_free_1   | table | postgres
 public | gis_osm_natural_free_1     | table | postgres
 public | gis_osm_places_a_free_1    | table | postgres
 public | gis_osm_places_free_1      | table | postgres
 public | gis_osm_pofw_a_free_1      | table | postgres
 public | gis_osm_pofw_free_1        | table | postgres
 public | gis_osm_pois_a_free_1      | table | postgres
 public | gis_osm_pois_free_1        | table | postgres
 public | gis_osm_railways_free_1    | table | postgres
 public | gis_osm_roads_free_1       | table | postgres
 public | gis_osm_traffic_a_free_1   | table | postgres
 public | gis_osm_traffic_free_1     | table | postgres
 public | gis_osm_transport_a_free_1 | table | postgres
 public | gis_osm_transport_free_1   | table | postgres
 public | gis_osm_water_a_free_1     | table | postgres
 public | gis_osm_waterways_free_1   | table | postgres
 public | spatial_ref_sys            | table | postgres
(19 rows)
```
Everything was successfully imported and the database is ready for spatial analysis.

### 2. Zistite, **aké kraje** sú na Slovensku (`planet_osm_polygon`, `admin_level = '4'`) a vypíšte súradnice **ťažiska (centroidu)** s `longitude` a `latitude`.

Using the table `planet_osm_polygon` (admin_level = 4), I selected all Slovak regions and calculated the centroid for each one (longitude and latitude).  

For the second task I dowloaded firstly  `osm2pgsql` and then planet_osm_polygon from the file slovakia-251028.osm.pbf.

```
PS C:\Users\sirad> osm2pgsql -d osm_slovakia `
>>   -U postgres `
>>   -H localhost `
>>   -P 5432 `
>>   -W `
>>   -S "C:\Program Files\osm2pgsql-bin\default.style" `
>>   --create --slim `
>>   --latlong `
>>   "C:\Users\sirad\PycharmProjects\PDT1\slovakia-251028.osm.pbf"
Password:
```
Now we have 7 more tables:

```
 public | planet_osm_line            | table | postgres
 public | planet_osm_nodes           | table | postgres
 public | planet_osm_point           | table | postgres
 public | planet_osm_polygon         | table | postgres
 public | planet_osm_rels            | table | postgres
 public | planet_osm_roads           | table | postgres
 public | planet_osm_ways            | table | postgres
```

Using the table `planet_osm_polygon` (admin_level = 4), I selected all Slovak regions and calculated the centroid for each one (longitude and latitude).  

```
SELECT
    name,
    ST_AsText(ST_Centroid(way)) AS centroid_text,
    ST_X(ST_Transform(ST_Centroid(way), 4326)) AS longitude,
    ST_Y(ST_Transform(ST_Centroid(way), 4326)) AS latitude
FROM planet_osm_polygon
WHERE admin_level = '4'
  AND boundary = 'administrative'
  AND name IS NOT NULL
ORDER BY name;

```
Result: 

```
Banskobystrický kraj,POINT(19.503924276992176 48.515727881298226),19.503924276992176,48.515727881298226
Bratislavský kraj,POINT(17.17906178926567 48.317412629626695),17.17906178926567,48.317412629626695
Košický kraj,POINT(21.26625345753445 48.697384109592),21.26625345753445,48.697384109592
Nitriansky kraj,POINT(18.31086705831648 48.14193211091358),18.31086705831648,48.14193211091358
Prešovský kraj,POINT(21.224596504541214 49.123652482877326),21.224596504541214,49.123652482877326
Trenčiansky kraj,POINT(18.213384569273117 48.85849549067472),18.213384569273117,48.85849549067472
Trnavský kraj,POINT(17.53483606404299 48.353009902443084),17.53483606404299,48.353009902443084
Žilinský kraj,POINT(19.17732002126666 49.17752692946),19.17732002126666,49.17752692946
```

I visualized the result in [geojson.io](https://geojson.io/). I did skript in python that generates .geojson, so here is it:  

<img width="1503" height="908" alt="image" src="https://github.com/user-attachments/assets/78cd07bb-dcef-46c1-9439-22ae281f6d42" />

All Slovak regions were displayed correctly with their centroids.

### 3. Zoraďte kraje podľa ich **veľkosti** (`st_area`) a zobrazte výsledok v **km²** v **SRID 5514**.

Next, I calculated the area of each region in **km²** using **EPSG:5514** (the Slovak coordinate system) and sorted them by size.

```
SELECT
    name,
    ST_Area(ST_Transform(way, 5514)) / 1000000 AS area_km2
FROM planet_osm_polygon
WHERE admin_level = '4'
  AND boundary = 'administrative'
  AND name IS NOT NULL
ORDER BY area_km2 DESC;
```
Result:
```
Banskobystrický kraj,9452.989813320259
Prešovský kraj,8971.239500496997
Žilinský kraj,6806.080122304121
Košický kraj,6750.868824298932
Nitriansky kraj,6342.459157679293
Trenčiansky kraj,4501.007201858132
Trnavský kraj,4145.250951910721
Bratislavský kraj,2051.69009137879
```

Visualization:  
<img width="663" height="636" alt="image" src="https://github.com/user-attachments/assets/712e01ff-0c8d-4e32-942a-ea227c089ee9" />

The largest region is **Banskobystrický kraj**, and the smallest one is **Bratislavský kraj**.

### 4. Pridajte si **dom, kde bývate**, ako **polygón** (napr. podľa Google Maps) do `planet_osm_polygon`. Dbajte na správny súradnicový systém. Výsledok zobrazte na mape.

I took coordinates from Google Maps and created my house polygon in `planet_osm_polygon` (+- 0.0002). The polygon is named **“Môj dom 2”** and it’s in the correct coordinate system (EPSG:4326).  

```
INSERT INTO planet_osm_polygon (osm_id, name, boundary, admin_level, way)
VALUES (
           -10000,
           'Môj dom 2',
           NULL,
           NULL,
           ST_GeomFromText(
                   'POLYGON((
                       17.12145 48.16003,
                       17.12165 48.16003,
                       17.12165 48.15983,
                       17.12145 48.15983,
                       17.12145 48.16003
                   ))',
                   4326
           )
       );


-- Check
SELECT name, ST_AsText(way)
FROM planet_osm_polygon
WHERE name = 'Môj dom 2';
```

```
Môj dom 2,"POLYGON((17.12145 48.16003,17.12165 48.16003,17.12165 48.15983,17.12145 48.15983,17.12145 48.16003))"
```

I checked it and visualized it in geojson.io:  
<img width="1151" height="851" alt="image" src="https://github.com/user-attachments/assets/251eb1fe-5011-4f0c-b760-f0e4f62c0d90" />

My house polygon was added correctly and appears in the right location.


### 5. Zistite, **v akom kraji** sa nachádza váš dom.

I checked which region contains my house polygon using a spatial join. The query showed that my house is located in **Bratislavský kraj**.

```
SELECT k.name AS kraj
FROM planet_osm_polygon AS k
         JOIN planet_osm_polygon AS d
              ON ST_Contains(k.way, d.way)
WHERE k.admin_level = '4'
  AND k.boundary = 'administrative'
  AND d.name = 'Môj dom 2';
```
```
Bratislavský kraj
```

For some cases I also did vizualization, but now tried in python.
<img width="689" height="371" alt="image" src="https://github.com/user-attachments/assets/37789a15-97b2-4c69-9768-0cc1a73a2746" />


### 6. Pridajte si do `planet_osm_point` vašu **aktuálnu polohu**. Dbajte na správny súradnicový systém. Výsledok zobrazte na mape.

Then I added my current position to the table `planet_osm_point` using coordinates (17.1211, 48.1601) in EPSG:4326. I named it **“My current location”**.

```
INSERT INTO planet_osm_point (osm_id, name, way)
VALUES (
           -9998,  -- фиктивный ID
           'My current location',
           ST_SetSRID(ST_MakePoint(17.1211, 48.1601), 4326)
       );

-- Check
SELECT name, ST_AsText(way)
FROM planet_osm_point
WHERE name = 'My current location';
```

```
My current location,POINT(17.1211 48.1601)
```

Visualization: 
<img width="731" height="701" alt="image" src="https://github.com/user-attachments/assets/a60f7833-02bb-4df9-a35c-6b5da85d17c7" />

My current location point is saved and displayed correctly.


### 7. Zistite, **či ste doma** – či je vaša poloha v rámci vášho polygónu bydliska.

I checked whether my current location point lies inside my house polygon. The query result was `true`, meaning my location is inside my home polygon.

```
SELECT
    p.name AS poloha,
    d.name AS dom,
    ST_Contains(d.way, p.way) AS ste_doma
FROM planet_osm_polygon AS d
         JOIN planet_osm_point AS p
              ON ST_Contains(d.way, p.way)
WHERE d.name = 'Môj dom 2'
  AND p.name = 'My current location';
```
```
My current location,Môj dom 2,true
```

Visualization:  
<img width="689" height="682" alt="image" src="https://github.com/user-attachments/assets/5af5305e-9bdb-4e78-be86-57ffe989867a" />


### 8. Zistite, ako ďaleko sa nachádzate od `Fakulta informatiky a informačných technológií STU`. Výpočet realizujte v správnom súradnicovom systéme.
Firstly lets see what is the name of FIIT in this table and then see the distance.

```
SELECT name FROM planet_osm_point
WHERE name ILIKE '%Fakulta informatiky%';

SELECT
    ROUND(
            ST_Distance(
                    ST_Transform(p.way, 5514),
                    ST_Transform(f.way, 5514)
            )::numeric, 2
    ) AS vzdialenost_m
FROM planet_osm_point AS p
         JOIN planet_osm_point AS f
              ON f.name = 'Slovenská technická univerzita v Bratislave, Fakulta informatiky a informačných technológií - Slovenská informatická knižnica'
WHERE p.name = 'My current location';
```
```
3760.11
```

So, I calculated the distance from my current location to **FIIT STU** (Faculty of Informatics and Information Technologies).  I used **EPSG:5514** for more accurate measurement. My current location is around **3.76 km** away from FIIT STU.

Visualization:  
<img width="689" height="682" alt="image" src="https://github.com/user-attachments/assets/011494a4-2642-46b8-8532-fbc192fea679" />


### 9. Pomocou **QGIS** vyplotujte **kraje** a **váš dom** z úlohy č. 2 (napr. červenou čiarou).

Unfortunatelly, I am not able to download QGIS, so I made the same visualization in [geojson.io](https://geojson.io/).
As I already done all queries for this (and also vizualizations), it was easy: just to to exporte all regions (admin_level = 4) and my house polygon into one GeoJSON file and viewed it online.

So, this square is my house.

<img width="1458" height="983" alt="image" src="https://github.com/user-attachments/assets/9fd60b0d-99a9-491e-917c-be0de44acdab" />

<img width="1452" height="1008" alt="image" src="https://github.com/user-attachments/assets/70586c0b-486f-465b-9784-52c9b65ecf45" />

<img width="1467" height="914" alt="image" src="https://github.com/user-attachments/assets/31c78e47-f46b-4e90-b857-0b9c199f913d" />

### 10. Zistite súradnice **ťažiska (centroidu)** plošne **najmenšieho okresu**, a uveďte aj **EPSG kód** súradnicového systému.

I looked for the smallest district (okres) in Slovakia (admin_level = 6), calculated its area and centroid, and also displayed the EPSG code.

```
SELECT
    name,
    ROUND((ST_Area(ST_Transform(way, 5514)) / 1000000)::numeric, 2) AS area_km2,
    ST_X(ST_Transform(ST_Centroid(way), 4326)) AS longitude,
    ST_Y(ST_Transform(ST_Centroid(way), 4326)) AS latitude,
    Find_SRID('public', 'planet_osm_polygon', 'way') AS epsg_code
FROM planet_osm_polygon
WHERE admin_level = '6'
  AND boundary = 'administrative'
  AND name IS NOT NULL
ORDER BY ST_Area(ST_Transform(way, 5514)) ASC
LIMIT 1;
```

```
Košice,243.68,21.228491092984687,48.703575030120014,4326
```

The smallest district is **Košice**, and its centroid coordinates are shown in EPSG:4326.

### 11. Vytvorte priestorovú tabuľku všetkých **úsekov ciest**, ktoré sa celé nachádzajú  do **10 km** od hranice okresov **Malacky** a **Pezinok**.  
Vytvorte ďalšiu tabuľku s úsekmi, ktoré túto hranicu **pretínajú alebo sa jej dotýkajú**. Výsledky overte v QGIS.

### 12. Jedným dotazom zistite **číslo a názov katastrálneho územia** (z dát ZBGIS: [https://www.geoportal.sk/sk/zbgis_smd/na-stiahnutie/](https://www.geoportal.sk/sk/zbgis_smd/na-stiahnutie/)), v ktorom sa nachádza **najdlhší úsek cesty (z dát OSM)** v **okrese, kde bývate**.

### 13. Vytvorte oblasť **Okolie_Bratislavy**, ktorá:
    - zahŕňa zónu do **20 km od Bratislavy**,
    - **neobsahuje Bratislavu I – V**,  
    - a je **len na území Slovenska**.  
    Zistite jej **výmeru**.


