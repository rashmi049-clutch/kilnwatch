"""
School-like places from Overture Maps (Places theme) for the study area, as a COMPARISON
layer for the register schools. Not used in any count.

Source: Overture Maps Foundation, Places theme (mostly Meta/Facebook pages, some Microsoft/Bing),
licence CDLA-Permissive-2.0. Read straight from the public S3 bucket with DuckDB; only rows
inside the study-area bbox are transferred, then clipped to the 24 NCR districts outside Delhi.

Known limits (tested 22 Oct 2026 around Katha/Saroorpur, Baghpat): government village schools
are largely absent; ~19% of school places sit on a shared point (town-centre geocodes); only
~5% of register schools had a name match within 200 m. So this layer can confirm some private
schools and point to missing ones, but its positions are not reliable.

Output: data/schools/overture_schools_ncr.gpkg (EPSG:32643)
        dashboard/public/data/overture_schools.json  [[lat, lon, name, category, confidence, stacked], ...]
"""
import json
from pathlib import Path

import duckdb
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
RELEASE = "2026-10-21.0"
W, S, E, N = 75.4738, 26.7061, 78.4775, 29.9934          # study-area bbox (WGS 84)
EDU = r"school|education|college|kindergarten|preschool|academy|university"

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
df = con.execute(f"""
    SELECT id, names.primary AS name, coalesce(taxonomy.primary, basic_category) AS category,
           confidence, sources[1].dataset AS source, ST_Y(geometry) AS lat, ST_X(geometry) AS lon
    FROM read_parquet('s3://overturemaps-us-west-2/release/{RELEASE}/theme=places/type=place/*', hive_partitioning=1)
    WHERE bbox.xmin BETWEEN {W} AND {E} AND bbox.ymin BETWEEN {S} AND {N}
      AND regexp_matches(lower(coalesce(taxonomy.primary, '') || ' ' || coalesce(basic_category, '')), '{EDU}')
""").df()
print(f"Overture school-like places in bbox: {len(df)}")

g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326).to_crs(32643)
dist = gpd.read_file(ROOT / "outputs/maps/district_exposure_32643.gpkg")
dist = dist[~dist.excluded.astype(bool)][["name", "geometry"]].rename(columns={"name": "district"})
g = gpd.sjoin(g, dist, predicate="within", how="inner").drop(columns="index_right")
# places sharing one exact coordinate are usually town-centre geocodes, not the building
g["stacked"] = g.groupby(["lat", "lon"]).id.transform("size") > 1
print(f"inside the 24 districts: {len(g)}  |  on a shared point: {int(g.stacked.sum())} ({100 * g.stacked.mean():.0f}%)")
print(g.source.value_counts().to_string())

out = ROOT / "data/schools/overture_schools_ncr.gpkg"
g.to_file(out, driver="GPKG")
rows = [[round(r.lat, 5), round(r.lon, 5), r.name or "", r.category or "", round(float(r.confidence or 0), 2), int(r.stacked)]
        for r in g.itertuples()]
(ROOT / "dashboard/public/data/overture_schools.json").write_text(json.dumps(rows, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
print(f"wrote {out.name} and overture_schools.json ({len(rows)} places)")
