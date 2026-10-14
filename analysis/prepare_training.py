"""
Day 2 (step 9) - Build a spatially honest train / val / test set.

Design:
  * TEST  = every SentinelKilnDB patch inside the NCR. The detector never
            sees NCR imagery during training.
  * TRAIN / VAL = patches in a 150 km ring around the NCR, split by 0.5 degree
            spatial blocks (80 / 20), so neighbouring overlapping patches
            cannot fall on both sides of the split.
  * A 2 km exclusion strip outside the NCR boundary is dropped from the
    ring: patches are 1.28 km wide and overlap, so a border kiln could
    otherwise appear in both train and test.
  * Background: kiln-free patches sampled from anywhere in the dataset
    (the ring has almost none), assigned to train/val by the same blocks.

Also measures leakage in the dataset's own random split: the share of its
test patches that overlap a train patch.

Outputs:
    data/kilns/yolo/{train,val,test}/{images,labels}/
    data/kilns/yolo/data.yaml
    outputs/tables/training_split.csv
"""

import io
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from PIL import Image
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "kilns" / "raw"
YOLO = ROOT / "data" / "kilns" / "yolo"
UTM = "EPSG:32643"

RING_KM, GAP_KM, BLOCK_DEG = 150, 2, 0.5
VAL_SHARE, NEG_RATIO, SEED = 0.2, 0.25, 42
PATCH_M = 1280


def dataset_leakage(idx: pd.DataFrame) -> float:
    """Share of the dataset's own test patches whose footprint overlaps a train patch."""
    g = gpd.GeoDataFrame(idx, geometry=gpd.points_from_xy(idx.lon, idx.lat), crs="EPSG:4326").to_crs(UTM)
    xy = np.c_[g.geometry.x, g.geometry.y]
    tr, te = xy[idx.split.eq("train").to_numpy()], xy[idx.split.eq("test").to_numpy()]
    # Two 1.28 km squares overlap if centres are closer than 1.28 km on both axes;
    # a Chebyshev distance query tests exactly that.
    d, _ = cKDTree(tr).query(te, p=np.inf)
    return float((d < PATCH_M).mean())


def assign(idx: pd.DataFrame, ncr) -> pd.DataFrame:
    g = gpd.GeoDataFrame(idx, geometry=gpd.points_from_xy(idx.lon, idx.lat), crs="EPSG:4326").to_crs(UTM)
    in_ncr = g.within(ncr)
    in_gap = g.within(ncr.buffer(GAP_KM * 1000)) & ~in_ncr
    in_ring = g.within(ncr.buffer(RING_KM * 1000)) & ~in_ncr & ~in_gap

    block = (np.floor(idx.lat / BLOCK_DEG).astype(int).astype(str) + "_" +
             np.floor(idx.lon / BLOCK_DEG).astype(int).astype(str))
    rng = np.random.default_rng(SEED)
    ublocks = block.unique()
    val_blocks = set(rng.choice(ublocks, int(len(ublocks) * VAL_SHARE), replace=False))
    fold = np.where(block.isin(val_blocks), "val", "train")

    role = pd.Series("unused", index=idx.index)
    role[in_ncr] = "test"
    role[in_ring & (idx.n_kilns > 0)] = pd.Series(fold, index=idx.index)[in_ring & (idx.n_kilns > 0)]

    # Background patches: kiln-free, outside NCR and the gap strip.
    n_pos = int((role.isin(["train", "val"])).sum())
    neg_pool = idx.index[(idx.n_kilns == 0) & ~in_ncr & ~in_gap]
    neg = rng.choice(neg_pool, min(len(neg_pool), int(n_pos * NEG_RATIO)), replace=False)
    role[neg] = pd.Series(fold, index=idx.index)[neg]

    out = idx.copy()
    out["role"], out["block"] = role, block
    return out


def export(sel: pd.DataFrame) -> None:
    for split in ("train", "val", "test"):
        for sub in ("images", "labels"):
            (YOLO / split / sub).mkdir(parents=True, exist_ok=True)

    for src in ("train", "val", "test"):
        want = sel[sel.split == src]
        if want.empty:
            continue
        roles = dict(zip(want.image_name, want.role))
        pf = pq.ParquetFile(RAW / f"{src}.parquet")
        for batch in pf.iter_batches(batch_size=2000, columns=["image_name", "image", "yolo_obb_label"]):
            b = batch.to_pandas()
            b = b[b.image_name.isin(roles)]
            for r in b.itertuples():
                role = roles[r.image_name]
                stem = r.image_name.removesuffix(".png")
                Image.open(io.BytesIO(r.image)).convert("RGB").save(YOLO / role / "images" / f"{stem}.png")
                (YOLO / role / "labels" / f"{stem}.txt").write_text("\n".join(r.yolo_obb_label))
        print(f"  exported from {src}")

    (YOLO / "data.yaml").write_text(
        f"path: {YOLO.as_posix()}\ntrain: train/images\nval: val/images\ntest: test/images\n"
        "names:\n  0: CFCBK\n  1: FCBK\n  2: Zigzag\n", encoding="utf-8")


def main() -> None:
    idx = pd.read_parquet(ROOT / "data" / "kilns" / "kilndb_index.parquet")
    ncr = gpd.read_file(ROOT / "data" / "boundaries" / "ncr_32643.gpkg").geometry.iloc[0]

    leak = dataset_leakage(idx)
    print(f"Dataset's own split: {leak:.1%} of test patches overlap a train patch")

    sel = assign(idx, ncr)
    used = sel[sel.role != "unused"]
    summary = used.groupby("role").agg(patches=("image_name", "size"),
                                       with_kilns=("n_kilns", lambda s: int((s > 0).sum())),
                                       kiln_boxes=("n_kilns", "sum"))
    print(summary)
    summary.assign(dataset_split_leakage=leak).to_csv(ROOT / "outputs" / "tables" / "training_split.csv")
    export(used)


if __name__ == "__main__":
    main()
