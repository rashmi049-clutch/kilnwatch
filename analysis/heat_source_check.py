"""
Non-kiln check 2 - is the heat inside a known non-kiln facility?
The firing test (SWIR hot spot) cannot tell a kiln from an airport apron, power
plant or furnace. Prompted by a 'kiln' on the IGI Airport apron, which a first
version of this script missed because OSM maps IGI as a multipolygon relation.
OSM features (ways AND relations, Overpass API): aeroway=aerodrome, power=plant,
man_made=works, landuse=industrial, amenity=crematorium.
Output: data/boundaries/osm_heat_sources_32643.gpkg
"""
from pathlib import Path
import time, requests, geopandas as gpd
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import polygonize, unary_union

ROOT = Path(__file__).resolve().parents[1]
URLS = ["https://overpass.kumi.systems/api/interpreter", "https://overpass-api.de/api/interpreter"]
ncr = gpd.read_file(ROOT / "data/boundaries/ncr_4326.geojson")
w, s, e, n = ncr.total_bounds
bb = f"({s},{w},{n},{e})"
# one query per tag: the combined query times out on the public servers
QUERIES = [f'nwr["aeroway"="aerodrome"]{bb};', f'nwr["power"="plant"]{bb};', f'nwr["man_made"="works"]{bb};',
           f'nwr["amenity"="crematorium"]{bb};', f'relation["landuse"="industrial"]{bb};', f'way["landuse"="industrial"]{bb};']


def kind(t):
    if t.get("aeroway") == "aerodrome": return "aerodrome"
    if t.get("power") == "plant": return "power_plant"
    if t.get("man_made") == "works": return "works"
    if t.get("amenity") == "crematorium": return "crematorium"
    return "industrial"


def geom(el):
    if el["type"] == "node":
        return Point(el["lon"], el["lat"])
    if el["type"] == "way":
        g = el.get("geometry") or []
        return Polygon([(p["lon"], p["lat"]) for p in g]) if len(g) >= 4 else None
    lines = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
             for m in el.get("members", []) if m.get("role") in ("outer", "") and m.get("geometry")]
    polys = list(polygonize(unary_union(lines))) if lines else []
    return unary_union(polys) if polys else None


def fetch(body):
    for attempt in range(6):
        u = URLS[attempt % 2]
        try:
            r = requests.post(u, data={"data": f"[out:json][timeout:300];({body});out geom;"}, timeout=400,
                              headers={"User-Agent": "KilnWatch research"})
            r.raise_for_status()
            return r.json()["elements"]
        except Exception as ex:
            print("  retry:", u, type(ex).__name__); time.sleep(20)
    raise RuntimeError(body)


els = []
for body in QUERIES:
    got = fetch(body); print(body.split("[")[1].split("]")[0], len(got)); els += got
rows = [{"osm": f"{el['type']}/{el['id']}", "kind": kind(el.get("tags", {})),
         "name": el.get("tags", {}).get("name", ""), "geometry": geom(el)} for el in els]
src = gpd.GeoDataFrame([x for x in rows if x["geometry"] is not None], crs=4326).to_crs(32643)
src["geometry"] = src.geometry.make_valid()
src["ha"] = src.area / 1e4
src.to_file(ROOT / "data/boundaries/osm_heat_sources_32643.gpkg")
print(src.groupby([src.kind, src.osm.str.split("/").str[0]]).size().to_string())
print(src[src.kind == "aerodrome"][["osm", "name", "ha"]].round(0).to_string())
