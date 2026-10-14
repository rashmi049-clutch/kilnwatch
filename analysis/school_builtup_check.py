"""
Step 6 (automated) - how far is each school point from any built-up land?

Visual check of 30 random schools (Rashmi, 29 Sep 2026): 16 of 30 points lie
on open land rather than on a building. A school is always a building, so
the distance from a point to the nearest built-up pixel is a lower bound on
its location error.

Built-up: ESA WorldCover 2021 v200, class 50 (built-up), 10 m.
Distance: Euclidean distance transform of the built-up mask, capped at 2 km,
sampled at every NCR school point.

Validation: the automated call (distance <= 50 m -> "building") against the
30 visual verdicts.

Output:
    data/schools/ncr_schools_32643.gpkg   adds dist_built_m
    outputs/tables/school_builtup_check.csv
"""

from pathlib import Path

import ee
import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CAP_M, SCALE, CHUNK = 2000, 10, 4000


def main() -> None:
    ee.Initialize(project="geosync-448701")
    wc = ee.ImageCollection("ESA/WorldCover/v200").first()
    built = wc.eq(50)
    # distance in pixels -> metres, via squared-distance transform
    dist = (built.fastDistanceTransform(int(CAP_M / SCALE), "pixels", "squared_euclidean")
            .sqrt().multiply(SCALE).rename("dist").reproject(crs="EPSG:32643", scale=SCALE))

    g = gpd.read_file(ROOT / "data" / "schools" / "ncr_schools_32643.gpkg")
    ll = g.to_crs(4326)
    vals = np.full(len(g), np.nan)
    for start in range(0, len(g), CHUNK):
        sub = ll.iloc[start:start + CHUNK]
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([p.x, p.y]), {"i": int(i)})
                                   for i, p in zip(sub.index, sub.geometry)])
        res = dist.sampleRegions(fc, scale=SCALE, geometries=False).getInfo()["features"]
        for f in res:
            vals[f["properties"]["i"]] = f["properties"].get("dist", np.nan)
        print(f"  {min(start + CHUNK, len(g))}/{len(g)}", flush=True)
    g["dist_built_m"] = np.minimum(vals, CAP_M)
    g.to_file(ROOT / "data" / "schools" / "ncr_schools_32643.gpkg", driver="GPKG")

    kept = g[g.use]
    bins = [-1, 0, 50, 100, 300, 800, CAP_M]
    labels = ["on built-up", "1-50 m", "51-100 m", "101-300 m", "301-800 m", "> 800 m"]
    dist_tab = pd.cut(kept.dist_built_m, bins, labels=labels).value_counts().reindex(labels)
    share = (100 * dist_tab / len(kept)).round(1)
    print("\nDistance from school point to nearest built-up (kept schools):")
    print(pd.DataFrame({"schools": dist_tab, "pct": share}).to_string())

    chk = gpd.read_file(ROOT / "data" / "schools" / "school_check_30.gpkg")
    chk = chk.merge(g[["schcd", "dist_built_m"]], on="schcd", how="left")
    chk["auto"] = np.where(chk.dist_built_m <= 50, "building", "open_land")
    agree = (chk.auto == chk.verdict).mean()
    print("\nAutomated vs visual (30 schools):")
    print(pd.crosstab(chk.verdict, chk.auto, rownames=["visual"], colnames=["automated"]))
    print(f"agreement {agree:.0%}")

    pd.DataFrame({"schools": dist_tab, "pct": share}).to_csv(ROOT / "outputs" / "tables" / "school_builtup_check.csv")
    chk[["check_id", "schname", "verdict", "dist_built_m", "auto"]].to_csv(
        ROOT / "outputs" / "tables" / "school_check_30_vs_auto.csv", index=False)


if __name__ == "__main__":
    main()
