"""
Day 1 - Assemble and verify the NCR boundary.

NCR is defined on pre-2023 Rajasthan districts, but OSM carries the 2023
splits. Reconstruction:

    old Bharatpur = Bharatpur + Deeg
    old Alwar     = Alwar + Khairthal-Tijara + (Kotputli-Behror inside old Alwar)

Kotputli-Behror was formed from parts of both Alwar and Jaipur, so it is cut
with the geoBoundaries ADM2 Alwar polygon. geoBoundaries was rejected for Delhi
because it follows a pre-2012 delineation, which is exactly what is wanted
here. Its lines are coarser than OSM's, so slivers under 5 km2 are dropped.

Verification gate: total must be within 1% of the NCR Planning Board's
stated 55,083 km2, and each reconstructed Rajasthan district within 1% of
its Census 2011 area.

Outputs:
    data/boundaries/ncr_districts_32643.gpkg   district polygons, UTM 43N
    data/boundaries/ncr_32643.gpkg             dissolved NCR outline
    data/boundaries/ncr_4326.geojson           same, for Earth Engine
"""

from pathlib import Path

import geopandas as gpd
from shapely.geometry import MultiPolygon

ROOT = Path(__file__).resolve().parents[1]
BND = ROOT / "data" / "boundaries"
GB = BND / "geoBoundaries-IND-ADM2.geojson"

AEA = "+proj=aea +lat_1=12 +lat_2=32 +lat_0=22 +lon_0=80 +datum=WGS84 +units=m"
UTM = "EPSG:32643"

NCRPB_KM2 = 55_083
CENSUS_KM2 = {"Alwar": 8_380, "Bharatpur": 5_066}   # Census 2011, to confirm
SLIVER_KM2 = 5


def drop_slivers(geom, min_km2=SLIVER_KM2):
    parts = geom.geoms if hasattr(geom, "geoms") else [geom]
    keep = [p for p in parts if p.area / 1e6 >= min_km2]
    return MultiPolygon(keep) if len(keep) > 1 else keep[0]


def main() -> None:
    osm = gpd.read_file(BND / "ncr_districts_osm_4326.gpkg").to_crs(AEA)
    gb = gpd.read_file(GB).to_crs(AEA)
    old_alwar_gb = gb.loc[gb.shapeName == "Alwar", "geometry"].iloc[0]

    def geom(name):
        return osm.loc[osm.district == name, "geometry"].iloc[0]

    kb_alwar = drop_slivers(geom("Kotputli-Behror").intersection(old_alwar_gb))
    alwar = geom("Alwar").union(geom("Khairthal-Tijara")).union(kb_alwar)
    bharatpur = geom("Bharatpur").union(geom("Deeg"))

    rows = osm[osm.state.isin(["Haryana", "Uttar Pradesh", "Delhi"])].copy()
    raj = gpd.GeoDataFrame(
        [{"district": "Alwar (pre-2023)", "state": "Rajasthan", "geometry": alwar},
         {"district": "Bharatpur (pre-2023)", "state": "Rajasthan", "geometry": bharatpur}],
        crs=AEA,
    )
    ncr = gpd.GeoDataFrame(
        gpd.pd.concat([rows[["district", "state", "geometry"]], raj], ignore_index=True),
        crs=AEA,
    )
    ncr["area_km2"] = ncr.area / 1e6

    print(ncr.groupby("state")["area_km2"].agg(["count", "sum"]).round(0))

    ok = True
    for name, ref in CENSUS_KM2.items():
        a = ncr.loc[ncr.district.str.startswith(name), "area_km2"].iloc[0]
        dev = 100 * (a - ref) / ref
        print(f"{name:10s} {a:8.0f} km2 vs Census {ref} -> {dev:+.2f}%")
        ok &= abs(dev) < 1

    total = ncr.dissolve().to_crs(AEA).area.iloc[0] / 1e6
    dev = 100 * (total - NCRPB_KM2) / NCRPB_KM2
    print(f"NCR total  {total:8.0f} km2 vs NCRPB {NCRPB_KM2} -> {dev:+.2f}%")
    ok &= abs(dev) < 1
    print("GATE:", "PASS" if ok else "FAIL")
    if not ok:
        raise SystemExit(1)

    ncr.to_crs(UTM).to_file(BND / "ncr_districts_32643.gpkg", driver="GPKG")
    outline = ncr.dissolve()[["geometry"]]
    outline.to_crs(UTM).to_file(BND / "ncr_32643.gpkg", driver="GPKG")
    outline.to_crs("EPSG:4326").to_file(BND / "ncr_4326.geojson", driver="GeoJSON")


if __name__ == "__main__":
    main()
