"""
Convert SentinelKilnDB oriented boxes inside the NCR into kiln points.

Each patch name gives its centre (lat, lon); a box centre (u, v) in 0-1 patch
coordinates sits (u - 0.5) * 1280 m east and (0.5 - v) * 1280 m north of it.
The authors cut patches from native Sentinel-2 grids, so positions carry an
error of a pixel or two (10-20 m) - small against a ~100 x 50 m kiln.

Overlapping patches repeat the same kiln; boxes of the same class within 60 m
are merged to one point (the mean position).

Output:
    data/kilns/kilndb_ncr_points_32643.gpkg   one point per kiln, class, n_views
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
UTM = "EPSG:32643"
PATCH_M, MERGE_M = 1280, 60
CLASSES = {0: "CFCBK", 1: "FCBK", 2: "Zigzag"}


def main() -> None:
    idx = pd.read_parquet(ROOT / "data" / "kilns" / "kilndb_index.parquet")
    names = set(idx.loc[idx.in_ncr, "image_name"])
    rows = []
    for split in ("train", "val", "test"):
        t = pq.read_table(ROOT / "data" / "kilns" / "raw" / f"{split}.parquet",
                          columns=["image_name", "yolo_obb_label"]).to_pandas()
        for r in t[t.image_name.isin(names)].itertuples():
            lat, lon = map(float, r.image_name.removesuffix(".png").split("_"))
            for lab in r.yolo_obb_label:
                p = lab.split()
                xy = np.array(p[1:9], float).reshape(4, 2)
                u, v = xy.mean(0)
                rows.append({"lat": lat, "lon": lon, "u": u, "v": v, "cls": int(p[0])})
    b = pd.DataFrame(rows)
    c = gpd.GeoSeries(gpd.points_from_xy(b.lon, b.lat), crs="EPSG:4326").to_crs(UTM)
    b["x"] = c.x + (b.u - 0.5) * PATCH_M
    b["y"] = c.y + (0.5 - b.v) * PATCH_M

    pts = []
    for cls, grp in b.groupby("cls"):
        tree = cKDTree(grp[["x", "y"]].to_numpy())
        n, lab = connected_components(tree.sparse_distance_matrix(tree, MERGE_M), directed=False)
        m = grp.assign(k=lab).groupby("k").agg(x=("x", "mean"), y=("y", "mean"), n_views=("x", "size"))
        m["cls"] = CLASSES[cls]
        pts.append(m)
    k = pd.concat(pts, ignore_index=True)
    g = gpd.GeoDataFrame(k, geometry=gpd.points_from_xy(k.x, k.y), crs=UTM)
    ncr = gpd.read_file(ROOT / "data" / "boundaries" / "ncr_32643.gpkg").geometry.iloc[0]
    g = g[g.within(ncr)].reset_index(drop=True)
    g.to_file(ROOT / "data" / "kilns" / "kilndb_ncr_points_32643.gpkg", driver="GPKG")
    print(f"{len(b):,} boxes -> {len(g):,} kilns inside NCR")
    print(g.cls.value_counts().to_string())
    print("views per kiln:", g.n_views.describe()[["mean", "max"]].round(2).to_dict())


if __name__ == "__main__":
    main()
