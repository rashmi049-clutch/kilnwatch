"""
Step 13 - Scan the whole NCR for kilns, one season at a time.

Each 1024 x 1024 px tile is cut into 128 px patches with a 30 px overlap
(stride 98) - the same patch size, overlap and per-patch min-max stretch the
detector was trained on. Detections are mapped to ground coordinates, then
merged across overlapping patches and tile edges: detections within 50 m of
each other are one kiln, kept at the highest confidence. Only kilns inside
the NCR boundary are kept.

Usage:
    python analysis/scan_ncr.py <season> <model.pt> [--limit N]
Output:
    data/kilns/detections_<season>_<model>.gpkg   one point per kiln
"""

import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
UTM = "EPSG:32643"
P, STRIDE, RES, CONF, MERGE_M, BATCH = 128, 98, 10, 0.25, 50, 64
CLASSES = {0: "CFCBK", 1: "FCBK", 2: "Zigzag"}


def norm(b):
    b = b.astype(np.float32)
    return ((b - b.min()) / (b.max() - b.min() + 1e-5) * 255).astype(np.uint8)


def starts(n):
    s = list(range(0, n - P + 1, STRIDE))
    if s[-1] != n - P:
        s.append(n - P)
    return s


def scan_tile(model, path: Path) -> list[dict]:
    with rasterio.open(path) as src:
        a = src.read()
        T = src.transform
    rows = []
    batch, meta = [], []

    def flush():
        if not batch:
            return
        for (r0, c0), res in zip(meta, model.predict(batch, imgsz=256, conf=CONF, device="cpu", verbose=False)):
            if res.obb is None or len(res.obb) == 0:
                continue
            for (u, v, w, h, ang), c, k in zip(res.obb.xywhr.numpy(), res.obb.conf.numpy(), res.obb.cls.numpy()):
                col, row = c0 + u, r0 + v
                x, y = T * (col, row)
                rows.append({"x": x, "y": y, "conf": float(c), "cls": CLASSES[int(k)],
                             "len_m": float(max(w, h) * RES), "wid_m": float(min(w, h) * RES)})
        batch.clear(); meta.clear()

    for r0 in starts(a.shape[1]):
        for c0 in starts(a.shape[2]):
            p = a[:, r0:r0 + P, c0:c0 + P]
            if (p[0] == 0).mean() > 0.2:
                continue
            batch.append(np.dstack([norm(p[i]) for i in (2, 1, 0)]))  # RGB -> BGR for ultralytics numpy input
            meta.append((r0, c0))
            if len(batch) == BATCH:
                flush()
    flush()
    return rows


def merge(df: pd.DataFrame) -> pd.DataFrame:
    tree = cKDTree(df[["x", "y"]].to_numpy())
    n, lab = connected_components(tree.sparse_distance_matrix(tree, MERGE_M), directed=False)
    df = df.assign(k=lab)
    best = df.loc[df.groupby("k").conf.idxmax()].copy()
    best["n_hits"] = df.groupby("k").size().reindex(best.k).to_numpy()
    return best.drop(columns="k")


def main() -> None:
    season, mpath = sys.argv[1], Path(sys.argv[2])
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    model = YOLO(str(mpath))
    tiles = sorted((ROOT / "data" / "s2" / season).glob("*.tif"))[:limit]
    rows, t0 = [], time.time()
    for i, t in enumerate(tiles, 1):
        rows += scan_tile(model, t)
        if i % 20 == 0 or i == len(tiles):
            print(f"  {season}: {i}/{len(tiles)} tiles, {len(rows)} raw detections, {time.time() - t0:.0f}s", flush=True)
    df = merge(pd.DataFrame(rows))
    g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.x, df.y), crs=UTM)
    ncr = gpd.read_file(ROOT / "data" / "boundaries" / "ncr_32643.gpkg").geometry.iloc[0]
    g = g[g.within(ncr)].reset_index(drop=True)
    tag = "" if limit is None else f"_test{limit}"
    out = ROOT / "data" / "kilns" / f"detections_{season}_{mpath.stem}{tag}.gpkg"
    g.to_file(out, driver="GPKG")
    print(f"{len(g)} kilns inside NCR -> {out.name}")
    print(g.cls.value_counts().to_string())


if __name__ == "__main__":
    main()
