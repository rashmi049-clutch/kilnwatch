"""
Non-kiln check 1 - is the heat seasonal?
Brick kilns stop firing in the monsoon (go/no-go test: 2% of monsoon scenes hot).
Refineries, furnaces, power plants and hot pavement stay hot year-round.
Monsoon hot frequency = share of clear Sentinel-2 scenes, Jul-Sep 2024 and
Jul-Sep 2025, with NHI_SWIR > 0 (max within 40 m). Monsoon scenes are cloudy,
so the scene filter is relaxed to 60% and clouds masked per pixel (QA60).
Sampled for the 3,447 firing-verified points and the 4,114 reference kilns,
whose distribution sets the cut-off.
Output: data/kilns/monsoon_heat.parquet
"""
from pathlib import Path
import ee, geopandas as gpd, numpy as np, pandas as pd
import firing_verify as fv

ROOT = Path(__file__).resolve().parents[1]
K = ROOT / "data" / "kilns"


def monsoon_image() -> ee.Image:
    def prep(img):
        qa = img.select("QA60")
        clear = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
        return img.normalizedDifference(["B12", "B11"]).gt(0).updateMask(clear).rename("hot")
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 60))
    col = s2.filterDate("2024-07-01", "2024-10-01").merge(s2.filterDate("2025-07-01", "2025-10-01")).map(prep)
    return col.mean().rename("hot_frac")


def cached(name, img, g):
    f = K / f"cache_monsoon_{name}_{len(g)}.npy"
    if f.exists():
        return np.load(f)
    v = fv.sample(img, g); np.save(f, v); return v


def main():
    ee.Initialize(project="geosync-448701")
    img = monsoon_image()
    det = gpd.read_file(K / "detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
    fk = det[det.fires].reset_index()          # 'index' = row in the filtered file
    ref = gpd.read_file(K / "kilndb_ncr_points_32643.gpkg")
    print("firing-verified points"); a = cached("fk", img, fk)
    print("reference kilns"); b = cached("ref", img, ref)
    out = pd.concat([pd.DataFrame({"group": "firing", "det_index": fk["index"], "monsoon_hot": a,
                                   "x": fk.geometry.x, "y": fk.geometry.y}),
                     pd.DataFrame({"group": "reference", "det_index": -1, "monsoon_hot": b,
                                   "x": ref.geometry.x, "y": ref.geometry.y})])
    out.to_parquet(K / "monsoon_heat.parquet")
    print(out.groupby("group").monsoon_hot.describe(percentiles=[.5, .9, .95, .99]).round(3).T)


if __name__ == "__main__":
    main()
