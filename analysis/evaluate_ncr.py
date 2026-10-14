"""
Step 11 - Score the detector on NCR kilns it never saw, and measure domain shift.

Test 1  Standard detection metrics (mAP50, mAP50-95, precision, recall) on all
        4,076 NCR test patches with the dataset's own imagery.

Test 2  Domain shift. The same NCR patches (random sample) scored twice:
          A. dataset imagery (single scene, the look the model trained on)
          B. this study's 2023-24 seasonal median, same ground window, same
             per-patch min-max stretch
        Scored by point matching, so both imagery sets are judged identically
        regardless of small grid differences: a detection is correct if its
        centre lies within 50 m of a reference kiln (kilndb_ncr_points), each
        reference matched at most once. Only the central 1,000 m of each patch
        is scored, so kilns cut by the patch edge do not count against either.

Output:
    outputs/tables/eval_ncr_standard.csv
    outputs/tables/eval_domain_shift.csv
"""

import io
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import rasterio
from PIL import Image
from pyproj import Transformer
from scipy.spatial import cKDTree
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models" / "kiln_obb_ring_v1_best.pt"
# override with --model <path>; results tagged with the model file name
UTM = "EPSG:32643"
PATCH_M, CORE_M, MATCH_M, CONF = 1280, 1000, 50, 0.25
N_SHIFT, SEED = 800, 11
TMP = ROOT / "data" / "eval_tmp"


def norm(b):
    return ((b - b.min()) / (b.max() - b.min() + 1e-5) * 255).astype(np.uint8)


def standard(model) -> pd.Series:
    m = model.val(data=str(ROOT / "data" / "kilns" / "yolo" / "data.yaml"), split="test",
                  imgsz=256, batch=16, device="cpu", workers=2, plots=False, verbose=False,
                  project=str(ROOT / "runs"), name="eval_ncr_test", exist_ok=True)
    s = pd.Series({"precision": m.box.mp, "recall": m.box.mr, "mAP50": m.box.map50, "mAP50_95": m.box.map})
    s.to_csv(ROOT / "outputs" / "tables" / "eval_ncr_standard.csv", header=["value"])
    return s


def build_pairs(idx: pd.DataFrame) -> pd.DataFrame:
    """Cut the same ground window from our composite for a sample of NCR test patches."""
    grid = gpd.read_file(ROOT / "data" / "s2" / "tile_grid_32643.gpkg")
    tr = Transformer.from_crs(4326, 32643, always_xy=True)
    # every NCR patch is in our test set, whichever split the dataset put it in
    test = idx[idx.in_ncr].sample(N_SHIFT, random_state=SEED).copy()
    test["cx"], test["cy"] = tr.transform(test.lon.values, test.lat.values)
    (TMP / "theirs").mkdir(parents=True, exist_ok=True)
    (TMP / "ours").mkdir(parents=True, exist_ok=True)

    img_bytes = {}
    for split, grp in test.groupby("split"):
        t = pq.read_table(ROOT / "data" / "kilns" / "raw" / f"{split}.parquet",
                          columns=["image_name", "image"],
                          filters=[("image_name", "in", grp.image_name.tolist())]).to_pandas()
        img_bytes.update(zip(t.image_name, t.image))
    keep = []
    for r in test.itertuples():
        hit = grid.cx[r.cx - 1:r.cx + 1, r.cy - 1:r.cy + 1]
        if hit.empty:
            continue
        tile = ROOT / "data" / "s2" / "s2324" / f"{hit.iloc[0].tile_id}.tif"
        with rasterio.open(tile) as src:
            row, col = src.index(r.cx, r.cy)
            if not (64 <= row <= src.height - 64 and 64 <= col <= src.width - 64):
                continue  # window would cross a tile edge; skip rather than stitch
            p = src.read(window=((row - 64, row + 64), (col - 64, col + 64)))
        stem = r.image_name.removesuffix(".png")
        Image.fromarray(np.dstack([norm(p[i]) for i in range(3)])).save(TMP / "ours" / f"{stem}.png")
        Image.open(io.BytesIO(img_bytes[r.image_name])).convert("RGB").save(TMP / "theirs" / f"{stem}.png")
        keep.append(r)
    return pd.DataFrame(keep)


def detections_to_ground(model, folder: Path, pairs: pd.DataFrame) -> pd.DataFrame:
    centre = {r.image_name.removesuffix(".png"): (r.cx, r.cy) for r in pairs.itertuples()}
    rows = []
    for res in model.predict(source=str(folder), imgsz=256, conf=CONF, device="cpu", stream=True, verbose=False):
        stem = Path(res.path).stem
        cx, cy = centre[stem]
        if res.obb is None or len(res.obb) == 0:
            continue
        for (u, v, w, h, a), c in zip(res.obb.xywhr.numpy(), res.obb.conf.numpy()):
            u, v = u / res.orig_shape[1], v / res.orig_shape[0]
            rows.append({"patch": stem, "x": cx + (u - 0.5) * PATCH_M, "y": cy + (0.5 - v) * PATCH_M, "conf": float(c)})
    return pd.DataFrame(rows)


def score(det: pd.DataFrame, pairs: pd.DataFrame, ref: np.ndarray) -> dict:
    half = CORE_M / 2
    tp = fp = fn = 0
    tree = cKDTree(ref)
    for r in pairs.itertuples():
        stem = r.image_name.removesuffix(".png")
        refs = tree.query_ball_point([r.cx, r.cy], r=half * 1.415)
        refs = [i for i in refs if abs(ref[i, 0] - r.cx) <= half and abs(ref[i, 1] - r.cy) <= half]
        d = det[(det.patch == stem)] if len(det) else det
        d = d[(abs(d.x - r.cx) <= half) & (abs(d.y - r.cy) <= half)] if len(d) else d
        used = set()
        for x, y in d.sort_values("conf", ascending=False)[["x", "y"]].to_numpy() if len(d) else []:
            best, bd = None, MATCH_M
            for i in refs:
                dd = np.hypot(ref[i, 0] - x, ref[i, 1] - y)
                if i not in used and dd <= bd:
                    best, bd = i, dd
            if best is None:
                fp += 1
            else:
                tp += 1
                used.add(best)
        fn += len(refs) - len(used)
    p, rc = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    return {"TP": tp, "FP": fp, "FN": fn, "precision": p, "recall": rc, "F1": 2 * p * rc / max(p + rc, 1e-9)}


def main() -> None:
    mpath = Path(sys.argv[sys.argv.index("--model") + 1]) if "--model" in sys.argv else MODEL
    model = YOLO(str(mpath))
    if "--skip-standard" not in sys.argv:
        print("Test 1 - standard metrics on NCR test patches (dataset imagery)")
        print(standard(model).round(3).to_string())

    idx = pd.read_parquet(ROOT / "data" / "kilns" / "kilndb_index.parquet")
    pairs = build_pairs(idx) if "--reuse-pairs" not in sys.argv else pd.read_csv(TMP / "pairs.csv")
    pairs.to_csv(TMP / "pairs.csv", index=False)
    ref = gpd.read_file(ROOT / "data" / "kilns" / "kilndb_ncr_points_32643.gpkg")
    ref_xy = np.c_[ref.geometry.x, ref.geometry.y]
    out = {}
    for name in ("theirs", "ours"):
        det = detections_to_ground(model, TMP / name, pairs)
        out[name] = score(det, pairs, ref_xy)
    t = pd.DataFrame(out).T
    t.index = ["A. dataset imagery", "B. our 2023-24 composite"]
    t.to_csv(ROOT / "outputs" / "tables" / f"eval_domain_shift_{mpath.stem}.csv")
    print(f"\nTest 2 - domain shift, {len(pairs)} NCR patches, point match within {MATCH_M} m")
    print(t.round(3).to_string())


if __name__ == "__main__":
    main()
