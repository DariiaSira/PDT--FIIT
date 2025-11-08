# PROTOCOL FOR TASK 3 -- Priestorové dáta PostGIS

**Author:** Dariia Sira  
**Date:** 2025-10-10  

---

## 1. Project Overview
Zadanie je zamerané na overenie vedomostí v oblasti PostGIS. Vašou úlohou bude vypracovať úlohy uvedené nižšie.

## 2. Solution

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
-- Find all Slovak regions (kraje)
-- I know that ST_Centroid sometimes gives a point outside of a polygon,
-- but for large regions it’s fine. If polygons were irregular, I’d use ST_PointOnSurface().
SELECT
    name,
    ST_AsText(ST_Centroid(way)) AS centroid_text,         -- centroid in text (POINT format)
    ST_X(ST_Transform(ST_Centroid(way), 4326)) AS longitude,  -- X = longitude in WGS84
    ST_Y(ST_Transform(ST_Centroid(way), 4326)) AS latitude   -- Y = latitude in WGS84
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
-- Here I calculate the area of each region in km².
-- I always transform to EPSG:5514 (meters), otherwise ST_Area gives nonsense in degrees.
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
-- coordinates must be (longitude latitude), not the other way around.
-- If I switch them, my house would appear in the wrong place.
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

-- Check if my house polygon was added correctly
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
-- I use ST_Contains, but it fails if the house touches the border. In that case I could use ST_Intersects instead.
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
-- I always set SRID when inserting custom data, otherwise PostGIS can’t calculate distances later.
INSERT INTO planet_osm_point (osm_id, name, way)
VALUES (
           -9998,  -- фиктивный ID
           'My current location',
           ST_SetSRID(ST_MakePoint(17.1211, 48.1601), 4326)
       );

--  Quick check – just to see that the point exists and looks OK.
SELECT name, ST_AsText(way)
FROM planet_osm_point
WHERE name = 'My current location';
```

```
My current location,POINT(17.1211 48.1601)
```

Visualization: 
<img width="1349" height="854" alt="image" src="https://github.com/user-attachments/assets/e62b71dc-1a66-4adf-995e-81dd0814a83a" />


My current location point is saved and displayed correctly.


### 7. Zistite, **či ste doma** – či je vaša poloha v rámci vášho polygónu bydliska.

I checked whether my current location point lies inside my house polygon. The query result was `true`, meaning my location is inside my home polygon.

```
-- if the point is exactly on the border, ST_Contains will return false. I could replace it with ST_Intersects if needed.
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
<img width="731" height="701" alt="image" src="https://github.com/user-attachments/assets/bd0e2701-9134-4014-95f0-3cef770d7a94" />



### 8. Zistite, ako ďaleko sa nachádzate od `Fakulta informatiky a informačných technológií STU`. Výpočet realizujte v správnom súradnicovom systéme.

Firstly lets see what is the name of FIIT in this table and then see the distance.

```
-- Names in OSM are long, so I use ILIKE with part of the text.
SELECT name FROM planet_osm_point
WHERE name ILIKE '%Fakulta informatiky%';

-- Very important: I always transform both geometries to EPSG:5514. If not, ST_Distance gives distance in degrees, not meters. Also, PostgreSQL needs CAST() when rounding a float value.
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
-- I find the smallest district (okres) in Slovakia and its centroid. I always transform to EPSG:5514 before calculating area (meters → km²).
-- If I forget ST_Transform, area will be totally wrong (it would be in degrees).
SELECT
    name,
    ROUND((ST_Area(ST_Transform(way, 5514)) / 1000000)::numeric, 2) AS area_km2,
    ST_X(ST_Transform(ST_Centroid(way), 4326)) AS longitude,
    ST_Y(ST_Transform(ST_Centroid(way), 4326)) AS latitude,
    Find_SRID('public', 'planet_osm_polygon', 'way') AS epsg_code
FROM planet_osm_polygon
WHERE admin_level = '6'   -- 6 = okres (district)
  AND boundary = 'administrative'
  AND name IS NOT NULL
ORDER BY ST_Area(ST_Transform(way, 5514)) ASC
LIMIT 1;
-- I sort from smallest to largest and pick the first one. For some multipolygons ST_Centroid might fall outside of the shape, but here it's fine, since districts are regular polygons.
```

```
Košice,243.68,21.228491092984687,48.703575030120014,4326
```

The smallest district is **Košice**, and its centroid coordinates are shown in EPSG:4326.

### 11. Vytvorte priestorovú tabuľku všetkých **úsekov ciest**, ktoré sa celé nachádzajú  do **10 km** od hranice okresov **Malacky** a **Pezinok**. Vytvorte ďalšiu tabuľku s úsekmi, ktoré túto hranicu **pretínajú alebo sa jej dotýkajú**. Výsledky overte v QGIS.

First, I created a spatial boundary between the districts **Malacky** and **Pezinok**. Then I built a **buffer zone** around this border (10 km) and used it to find two sets of roads:

1. All road segments that lie entirely **within 10 km** of the border.  
2. All road segments that **touch or cross** the border.

To improve precision, I worked in **EPSG:5514**, which measures distances in meters.  
`ST_Within()` checks if a geometry is completely inside another, while `ST_Intersects()` detects if two geometries touch or overlap.


```
-- I create a buffer zone (20 km) around the boundary between Malacky and Pezinok. I use EPSG:5514 because buffer distance (20,000) must be in meters, not degrees.

CREATE VIEW hranica_malacky_pezinok_buffer AS
SELECT ST_Buffer(ST_Transform(geom, 5514), 20000) AS geom
FROM hranica_malacky_pezinok;

-- I check that buffer looks OK.
SELECT ST_GeometryType(geom), ST_Area(geom)
FROM hranica_malacky_pezinok_buffer;


-- Now I create a table with all roads located completely within 10 km of the boundary. ST_Within means the *entire* geometry is inside the buffer.
-- Sometimes it's better to use ST_DWithin if I want partial overlap (faster too).
CREATE TABLE roads_within_10km AS
SELECT l.*
FROM planet_osm_line AS l
         JOIN hranica_malacky_pezinok_buffer AS h
              ON ST_Within(ST_Transform(l.way, 5514), h.geom)
WHERE l.highway IS NOT NULL;  -- I keep only real roads

-- Roads that touch or cross the boundary. ST_Intersects returns TRUE also for touching geometries. I transform both sides to EPSG:5514 to be precise.
CREATE TABLE roads_touch_or_cross AS
SELECT l.*
FROM planet_osm_line AS l
         JOIN hranica_malacky_pezinok AS h
              ON ST_Intersects(ST_Transform(l.way, 5514), ST_Transform(h.geom, 5514))
WHERE l.highway IS NOT NULL;

-- Quick check of counts to see if I got data.
SELECT COUNT(*) AS pocet_v_10km FROM roads_within_10km;   -- result: 85515
SELECT COUNT(*) AS pocet_prienik FROM roads_touch_or_cross; -- result: 100
-- If both counts are 0, it usually means the boundary geometries (Malacky/Pezinok), were not found or have wrong admin_level.
```

After running the queries, both spatial tables were created successfully:  
- `roads_within_10km`  
- `roads_touch_or_cross`

I visualized the result in Python to confirm that the geometries matched correctly with the district borders.

<img width="795" height="858" alt="image" src="https://github.com/user-attachments/assets/a4809613-9df6-47a4-a8f6-4e52d1ee3f4d" />

This task helped to understand how proximity and intersection work in PostGIS — two essential spatial operations. The buffer defines the “influence area,” and by joining it with roads, I could isolate all roads near the boundary and those that physically cross it.

### 12. Jedným dotazom zistite **číslo a názov katastrálneho územia** (z dát ZBGIS: [https://www.geoportal.sk/sk/zbgis_smd/na-stiahnutie/](https://www.geoportal.sk/sk/zbgis_smd/na-stiahnutie/)), v ktorom sa nachádza **najdlhší úsek cesty (z dát OSM)** v **okrese, kde bývate**.

At first, I couldn’t open the provided ZBGIS link, so I found a similar dataset on the official [GKU website](https://www.gku.sk/gku/produkty-sluzby/na-stiahnutie/zbgis.html).  
It contained several layers, including **“Geografický názov – Katastrálne územie”**, which lists cadastral areas of Slovakia.  
I downloaded and imported it into PostgreSQL as a table called `zbgis_katastralne_uzemia`.

```
import geopandas as gpd
from sqlalchemy import create_engine

engine = create_engine("postgresql://postgres:postgres@localhost:5432/osm_slovakia")

gdf = gpd.read_file(r"C:\Users\sirad\PycharmProjects\PDT1\gn_shp\GNKU.shp")
gdf.to_postgis("zbgis_katastralne_uzemia", engine, if_exists="replace", index=False)

print("✅ GNKU (katastrálne územia) bolo úspešne importované do PostGIS!")
```

To make the queries faster, I created **GIST spatial indexes** on all geometry columns — this helps PostGIS skip unnecessary geometry checks.

```
-- task 12
-- I prepare indexes first — they speed up spatial queries massively.
-- Without them, ST_Within and ST_DWithin are very slow.
CREATE INDEX IF NOT EXISTS idx_osm_line_geom
    ON planet_osm_line USING GIST (way);
CREATE INDEX IF NOT EXISTS idx_osm_polygon_geom
    ON planet_osm_polygon USING GIST (way);
CREATE INDEX IF NOT EXISTS idx_zbgis_kat_geom
    ON zbgis_katastralne_uzemia USING GIST (geometry);

-- I find the longest road in the Bratislava district and the cadastral area (ZBGIS) where it is.
-- I merge all Bratislava parts (I–V) using ST_Union, otherwise the query returns nothing.
-- I use ST_DWithin instead of ST_Intersects because ZBGIS geometries are points (centroids).
WITH bratislava_okres AS (
    SELECT ST_Union(way) AS geom
    FROM planet_osm_polygon
    WHERE name ILIKE 'Bratislava%' AND admin_level IN ('6','9')
)
SELECT
    z."IDN5" AS cislo_katastra,
    z."NM5" AS nazov_katastra,
    ROUND(CAST(ST_Length(ST_Transform(r.way, 5514)) / 1000 AS numeric), 2) AS dlzka_km
FROM planet_osm_line AS r
         JOIN bratislava_okres AS o
              ON ST_Within(ST_Centroid(r.way), o.geom)
         JOIN zbgis_katastralne_uzemia AS z
              ON ST_DWithin(
                      ST_Transform(ST_Centroid(r.way), 5514),
                      ST_Transform(z.geometry, 5514),
                      500
                 )
WHERE r.highway IS NOT NULL
ORDER BY ST_Length(ST_Transform(r.way, 5514)) DESC
LIMIT 1;
-- The 500-meter tolerance is needed because GNKU points (ZBGIS) are centroids, not polygons.
-- I also transform to EPSG:5514 for correct length in meters.
```

Then I prepared the main query:
- First, I merged all polygons of **Bratislava** (and its municipal parts) into one geometry using `ST_Union()`.
- Then, I selected all OSM road segments whose **centroid** lies within Bratislava’s boundary (`ST_Within()`).
- Next, I joined these roads to the **nearest cadastral unit** from ZBGIS using `ST_DWithin()` with a 500 m tolerance — because the GNKU layer stores cadastral centroids as points.
- Finally, I sorted the results by road length in descending order and limited the output to the longest segment.

```
870293,Vrakuňa,5.06
```

So, the longest road segment in Bratislava is located in the cadastral area **Vrakuňa**, and it is approximately **5.06 km** long.

This query combines both **topological filtering** (roads inside Bratislava) and **spatial proximity** (nearest cadastral centroid). Indexing was crucial here — without it, the query took a very long time to run.

### 13. Vytvorte oblasť **Okolie_Bratislavy**, ktorá:
    - zahŕňa zónu do **20 km od Bratislavy**,
    - **neobsahuje Bratislavu I – V**,  
    - a je **len na území Slovenska**.  
    Zistite jej **výmeru**.

**My approach:**
1. I found the main **Bratislava polygon** (`admin_level = 6`).
2. I created a **20 km buffer** around it (`ST_Buffer()`).
3. Then I collected all Bratislava subdistricts (`Bratislava-…`), except *Bratislava predmestie*, and merged them using `ST_Union()`.
4. I subtracted these inner parts from the buffer using `ST_Difference()` — this removed the city itself.
5. I clipped the result with the boundary of Slovakia (`ST_Intersection()`).
6. Finally, I calculated the total area in **km²** (EPSG:5514).

Firstly lets check names Bratislava in the table:

```
-- Check what we have in table
SELECT name, admin_level
FROM planet_osm_polygon
WHERE name ILIKE 'Bratislava%';
```

```
Bratislava,
Bratislava,
Bratislava,
Bratislava Business Park,
Bratislava-Petržalka,
Bratislava-Petržalka,
Bratislava,
Bratislava,
Bratislava,
Bratislava-Rača,
Bratislava-Rača,
Bratislava 35,
Bratislava-Vajnory,
Bratislava Business Center V,
Bratislava Business Center IV,
Bratislava Business Center III,
Bratislava Business Center I Plus,
Bratislava Business Center I,
Bratislava – Filiálka,
Bratislava-Filiálka,
Bratislava-Nové Mesto,
Bratislava-Nové Mesto,
Bratislava-Nové Mesto,
Bratislava-Nové Mesto,
Bratislava predmestie,
Bratislava predmestie,
Bratislava-Vinohrady,
Bratislava 1 - 811 04,
Bratislava hlavná stanica,
Bratislava hl.st.,
Bratislava hl.st.,
Bratislava hl.st.,
Bratislava hl.st.,
Bratislava hl.st.,
Bratislava hl.st.,
Bratislava 1 - 811 05,
Bratislava,
Bratislava,
Bratislava 1 - 811 07,
Bratislava 1 - 811 05,
Bratislava - mestská časť Staré Mesto,9
Bratislava 1 - 811 02,
Bratislava 1 - 811 06,
Bratislava 1 - 811 03,
Bratislava 1 - 811 01,
Bratislava 1 - 811 08,
Bratislava 1 - 811 09,
Bratislava,6
Bratislava - Lamač,
Bratislava-Lamač,
Bratislava-Lamač,
Bratislava IV - 841 01,
Bratislava IV - 841 02,
Bratislava IV - 841 01,
Bratislava 48,
Bratislava,
```

We see the dataset contained many “Bratislava” entries — including railway stations, postal codes, and business centers. Only the administrative polygons with names like *Bratislava I–V* were relevant to exclude. Since *Bratislava predmestie* lies outside those city parts, I kept it.

```
-- I create the “Okolie Bratislavy” area. All buffers and differences must be in 5514 (meters), never 4326.

-- Select the Bratislava polygon
CREATE OR REPLACE VIEW bratislava_okres AS
SELECT way AS geom
FROM planet_osm_polygon
WHERE name = 'Bratislava' AND admin_level = '6';

-- Create 20 km buffer around Bratislava
CREATE OR REPLACE VIEW bratislava_buffer AS
SELECT ST_Buffer(ST_Transform(geom, 5514), 20000) AS geom
FROM bratislava_okres;

-- Combine all parts of Bratislava (I–V) except "predmestie"
-- I exclude everything with name ILIKE 'Bratislava%' except the “predmestie” area.
CREATE OR REPLACE VIEW bratislava_casti AS
SELECT ST_Union(way) AS geom
FROM planet_osm_polygon
WHERE name ILIKE 'Bratislava%'
  AND name NOT ILIKE '%predmestie%'
  AND admin_level = '9';

-- Subtract Bratislava (and its parts) from the 20 km buffer
CREATE OR REPLACE VIEW okolie_bratislavy_raw AS
SELECT ST_Difference(
               (SELECT geom FROM bratislava_buffer),
               ST_Transform((SELECT ST_Union(geom) FROM bratislava_casti), 5514)
       ) AS geom;

-- Cut the buffer by Slovakia boundary so it doesn’t go outside the country
CREATE OR REPLACE VIEW okolie_bratislavy AS
SELECT ST_Intersection(
               (SELECT geom FROM okolie_bratislavy_raw),
               ST_Transform(
                       (SELECT way FROM planet_osm_polygon
                        WHERE name ILIKE '%Slovensk%' AND admin_level = '2'),
                       5514
               )
       ) AS geom;

-- Calculate the area in km²
SELECT
    ROUND((ST_Area(geom) / 1000000)::numeric, 2) AS vymera_km2
FROM okolie_bratislavy;
-- My result was 1838.07 km².
-- ⚠️ If area = NULL, it usually means intersection failed because
-- some geometry had invalid SRID or different coordinate system.

```

```
1838.07
```
Visualization:
<img width="1411" height="999" alt="image" src="https://github.com/user-attachments/assets/fe20b4cb-08f4-4bc7-b53c-d6d0716e0f60" />


The resulting polygon represents the **Bratislava surroundings** — the region within 20 km around the capital, excluding the city and limited to Slovak territory. This area could be useful for analyzing suburban development, commuting zones, or environmental studies around Bratislava.

---

I successfully completed all the tasks. Each assignment was supplemented with visualization — either in Python (using GeoPandas and Matplotlib) or in geojson.io, even in cases where visualization was not explicitly required. During the work, I encountered several technical issues (for example, slow queries without indexes, a broken ZBGIS link, and the inability to install QGIS), but I solved all of them using alternative approaches. The biggest challenge was optimizing query performance and correctly transforming coordinate systems between EPSG:4326 and EPSG:5514. Overall, I successfully completed the entire project — all results were verified and visually presented.


