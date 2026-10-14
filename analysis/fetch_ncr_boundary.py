"""
Day 1 - Build the National Capital Region boundary from OpenStreetMap districts.

NCR as defined by the NCR Planning Board: Delhi NCT plus 14 districts of
Haryana, 8 of Uttar Pradesh and 2 of Rajasthan (Alwar, Bharatpur), stated
area 55,083 km2.

Rajasthan complication: in 2023 Alwar and Bharatpur were split to create
Khairthal-Tijara, Kotputli-Behror (partly from Jaipur) and Deeg. NCR is still
defined on the pre-2023 districts, so the new districts are fetched too and
their areas reported, so the right combination can be chosen on evidence.

Delhi NCT is reused from ../delhi-vegetation-change (verified there at
1,478 km2, -0.34% vs published).

Output:
    data/boundaries/ncr_districts_osm_4326.gpkg   every fetched district
"""

import json
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import linemerge, polygonize, unary_union

ROOT = Path(__file__).resolve().parents[1]
BND = ROOT / "data" / "boundaries"
CACHE = BND / "osm_ncr_districts_raw.json"
DELHI = BND / "delhi_nct_4326.geojson"   # copied from the Delhi vegetation project

MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
HEADERS = {"User-Agent": "ncr-brick-kilns/1.0 (GIS portfolio project)"}

# OSM admin_level=5 relation ids, found by name search within each state.
DISTRICTS = {
    # Haryana (14)
    "Faridabad": ("Haryana", 1943060), "Gurugram": ("Haryana", 3577685),
    "Nuh": ("Haryana", 9514809), "Rohtak": ("Haryana", 1942937),
    "Sonipat": ("Haryana", 1942904), "Rewari": ("Haryana", 1942991),
    "Jhajjar": ("Haryana", 1942946), "Panipat": ("Haryana", 1942866),
    "Palwal": ("Haryana", 9514899), "Bhiwani": ("Haryana", 1942977),
    "Charkhi Dadri": ("Haryana", 9520279), "Mahendragarh": ("Haryana", 1942988),
    "Jind": ("Haryana", 1942917), "Karnal": ("Haryana", 1942858),
    # Uttar Pradesh (8)
    "Meerut": ("Uttar Pradesh", 1958010), "Ghaziabad": ("Uttar Pradesh", 1958054),
    "Gautam Buddha Nagar": ("Uttar Pradesh", 1958053),
    "Bulandshahr": ("Uttar Pradesh", 1958144), "Baghpat": ("Uttar Pradesh", 1958008),
    "Hapur": ("Uttar Pradesh", 9539177), "Shamli": ("Uttar Pradesh", 9539710),
    "Muzaffarnagar": ("Uttar Pradesh", 1958011),
    # Rajasthan (2 NCR districts + the 2023 splits)
    "Alwar": ("Rajasthan", 1950060), "Bharatpur": ("Rajasthan", 1950061),
    "Deeg": ("Rajasthan", 16700632), "Khairthal-Tijara": ("Rajasthan", 16700901),
    "Kotputli-Behror": ("Rajasthan", 16700872),
}


def overpass(query: str) -> dict:
    last = None
    for url in MIRRORS:
        try:
            r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=600)
            if r.ok:
                print(f"  fetched via {url}")
                return r.json()
            last = f"{url} -> HTTP {r.status_code}"
        except Exception as e:
            last = f"{url} -> {type(e).__name__}"
        print(f"  {last}")
    raise SystemExit(f"All Overpass mirrors failed. Last: {last}")


def fetch_raw() -> dict:
    if CACHE.exists():
        print(f"Using cached {CACHE.name}")
        return json.loads(CACHE.read_text(encoding="utf-8"))
    ids = ",".join(str(v[1]) for v in DISTRICTS.values())
    print("Querying Overpass...")
    data = overpass(f"[out:json][timeout:600];rel(id:{ids});out geom;")
    CACHE.write_text(json.dumps(data), encoding="utf-8")
    return data


def build_polygon(relation: dict):
    """Assemble a relation's member ways into a (Multi)Polygon."""
    def rings(role: str):
        lines = [
            [(p["lon"], p["lat"]) for p in m["geometry"]]
            for m in relation.get("members", [])
            if m.get("type") == "way" and m.get("role") == role and m.get("geometry")
        ]
        if not lines:
            return []
        merged = linemerge(lines)
        parts = merged.geoms if merged.geom_type == "MultiLineString" else [merged]
        return list(polygonize(parts))

    outer = rings("outer")
    if not outer:
        return None
    shell = unary_union(outer)
    inner = rings("inner")
    if inner:
        shell = shell.difference(unary_union(inner))
    return shell if isinstance(shell, (Polygon, MultiPolygon)) else None


def main() -> None:
    data = fetch_raw()
    by_id = {e["id"]: e for e in data["elements"] if e.get("type") == "relation"}

    rows = []
    for name, (state, rel_id) in DISTRICTS.items():
        rel = by_id.get(rel_id)
        geom = build_polygon(rel) if rel else None
        if geom is None or geom.is_empty:
            print(f"  FAILED {name} (rel {rel_id})")
            continue
        rows.append({"district": name, "state": state, "osm_rel": rel_id, "geometry": geom})

    delhi = gpd.read_file(DELHI).to_crs("EPSG:4326")
    rows.append({"district": "Delhi NCT", "state": "Delhi", "osm_rel": None,
                 "geometry": delhi.union_all()})

    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    # Areas in an equal-area CRS (India-centred Albers), never in degrees.
    aea = "+proj=aea +lat_1=12 +lat_2=32 +lat_0=22 +lon_0=80 +datum=WGS84 +units=m"
    gdf["area_km2"] = gdf.to_crs(aea).area / 1e6
    gdf.to_file(BND / "ncr_districts_osm_4326.gpkg", driver="GPKG")

    print(gdf[["state", "district", "area_km2"]].round(0).to_string(index=False))


if __name__ == "__main__":
    main()
