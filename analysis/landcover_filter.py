"""
Step 13b - Land-cover filter for detections.

Diagnosis (29 Sep 2026): detections matching a reference kiln sit on WorldCover
bare (68%) or grass/open (26%) ground; unmatched detections mostly on cropland
(48%), trees/shrub (11%) and built-up (9%). A kiln's footprint is a bare brick
yard, so the share of bare + grass pixels around a detection separates the two.

Feature: fraction of ESA WorldCover 2021 pixels within 40 m that are bare (60)
or grassland (30). Threshold: chosen from the data, as the value maximising F1
against the reference on detections inside reference-covered patches only
(where the reference is complete enough to judge). Applied to all detections.

Known cost: WorldCover is 2021; a kiln built on cropland after 2021 can be
dropped.

Output:
    adds column open_frac to detections_*.gpkg, writes *_filtered.gpkg
    outputs/tables/landcover_filter_threshold.csv
"""

import sys
from pathlib import Path

import ee
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
MODEL = "kiln_obb_ring_v1_best"
BUF, CHUNK, MATCH_M = 40, 3000, 50


def open_fraction(g: gpd.GeoDataFrame) -> np.ndarray:
    wc = ee.ImageCollection("ESA/WorldCover/v200").first()
    open_ = wc.eq(60).Or(wc.eq(30)).rename("open")
    ll = g.to_crs(4326)
    out = np.full(len(g), np.nan)
    for s in range(0, len(g), CHUNK):
        sub = ll.iloc[s:s + CHUNK]
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([p.x, p.y]).buffer(BUF), {"i": int(i)})
                                   for i, p in zip(sub.index, sub.geometry)])
        res = open_.reduceRegions(fc, ee.Reducer.mean(), scale=10).getInfo()["features"]
        for f in res:
            out[f["properties"]["i"]] = f["properties"].get("mean", np.nan)
        print(f"  {min(s + CHUNK, len(g))}/{len(g)}", flush=True)
    return out


def main() -> None:
    ee.Initialize(project="geosync-448701")
    ref = gpd.read_file(ROOT / "data" / "kilns" / "kilndb_ncr_points_32643.gpkg")
    R = np.c_[ref.geometry.x, ref.geometry.y]
    idx = pd.read_parquet(ROOT / "data" / "kilns" / "kilndb_index.parquet")
    idx = idx[idx.in_ncr]
    pc = gpd.GeoSeries(gpd.points_from_xy(idx.lon, idx.lat), crs=4326).to_crs(32643)
    ptree = cKDTree(np.c_[pc.x, pc.y])

    thr = None
    for season in ("s2324", "s2526"):
        path = ROOT / "data" / "kilns" / f"detections_{season}_{MODEL}.gpkg"
        g = gpd.read_file(path)
        if "open_frac" not in g:
            g["open_frac"] = open_fraction(g)
            g.to_file(path, driver="GPKG")
        if thr is None:  # calibrate once, on the 2023-24 season (reference period)
            D = np.c_[g.geometry.x, g.geometry.y]
            g["near_ref"] = cKDTree(R).query(D)[0] <= MATCH_M
            g["in_ref"] = ptree.query(D, p=np.inf)[0] <= 500
            cal = g[g.in_ref]
            refs_in = (ptree.query(R, p=np.inf)[0] <= 500).sum()
            rows = []
            for t in np.arange(0.0, 0.81, 0.05):
                keep = cal[cal.open_frac >= t]
                tp = int(keep.near_ref.sum())
                p = tp / max(len(keep), 1)
                r = tp / refs_in
                rows.append({"threshold": round(t, 2), "kept": len(keep), "precision": p, "recall": r,
                             "F1": 2 * p * r / max(p + r, 1e-9)})
            tab = pd.DataFrame(rows)
            tab.to_csv(ROOT / "outputs" / "tables" / "landcover_filter_threshold.csv", index=False)
            print(tab.round(3).to_string(index=False))
            thr = float(tab.loc[tab.F1.idxmax(), "threshold"])
            print(f"chosen threshold (max F1): open_frac >= {thr}")
        f = g[g.open_frac >= thr].drop(columns=[c for c in ("near_ref", "in_ref") if c in g], errors="ignore")
        f.to_file(path.with_name(path.stem + "_filtered.gpkg"), driver="GPKG")
        print(f"{season}: {len(g)} -> {len(f)} after filter")


if __name__ == "__main__":
    main()
