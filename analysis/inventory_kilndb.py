"""
Day 1 - Inventory SentinelKilnDB labels without downloading images.

Reads only the name and label columns of each split over HTTP, parses the
lat/lon encoded in each image name, and counts patches and kilns inside
the NCR and in a 150 km ring around it.

Image names are "lat_lon.png"; whether that point is the patch centre or a
corner is checked in inspect step later - for an inventory at this scale
(128 px x 10 m = 1.28 km patches) the difference does not matter.

Output:
    data/kilns/kilndb_index.parquet   one row per patch: split, lat, lon, n_kilns, classes
"""

from pathlib import Path

import fsspec
import geopandas as gpd
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://huggingface.co/datasets/SustainabilityLabIITGN/SentinelKilnDB/resolve/main"
UTM = "EPSG:32643"


def read_labels(split: str) -> pd.DataFrame:
    with fsspec.open(f"{BASE}/{split}/{split}.parquet", block_size=2**20).open() as f:
        t = pq.ParquetFile(f).read(columns=["image_name", "yolo_obb_label"]).to_pandas()
    t["split"] = split
    return t


def main() -> None:
    df = pd.concat([read_labels(s) for s in ("train", "val", "test")], ignore_index=True)
    ll = df.image_name.str.removesuffix(".png").str.split("_", expand=True).astype(float)
    df["lat"], df["lon"] = ll[0], ll[1]
    df["n_kilns"] = df.yolo_obb_label.apply(len)
    df["classes"] = df.yolo_obb_label.apply(lambda L: ",".join(sorted({s.split()[0] for s in L})))
    df = df.drop(columns="yolo_obb_label")

    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs="EPSG:4326").to_crs(UTM)
    ncr = gpd.read_file(ROOT / "data" / "boundaries" / "ncr_32643.gpkg").geometry.iloc[0]
    pts["in_ncr"] = pts.within(ncr)
    pts["in_ring150"] = pts.within(ncr.buffer(150_000)) & ~pts.in_ncr

    out = pd.DataFrame(pts.drop(columns="geometry"))
    out.to_parquet(ROOT / "data" / "kilns" / "kilndb_index.parquet", index=False)

    print(f"Patches: {len(out):,}   kilns: {out.n_kilns.sum():,}")
    for zone in ("in_ncr", "in_ring150"):
        z = out[out[zone]]
        print(f"\n{zone}: {len(z):,} patches, {(z.n_kilns > 0).sum():,} with kilns, {z.n_kilns.sum():,} kiln boxes")
        print(z.groupby("split").n_kilns.agg(["count", "sum"]).rename(columns={"count": "patches", "sum": "kilns"}))
    lab = out[out.in_ncr & (out.n_kilns > 0)]
    print("\nClass mix in NCR patches:")
    print(lab.classes.str.split(",").explode().value_counts())


if __name__ == "__main__":
    main()
