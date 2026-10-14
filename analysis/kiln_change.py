"""
Step 14 - Which kilns kept firing, which stopped, which are new (2023-24 -> 2025-26).

Change is measured by firing at fixed locations, not by re-detection, so the
detector's ~35% miss rate cannot masquerade as closures.

  continuing : firing-verified in 2023-24 (hot_frac >= 0.12) and still >= 0.12
               in the 2025-26 firing season at the same place
  stopped    : firing-verified in 2023-24, < 0.12 in 2025-26
  new        : filtered 2025-26 detection that fires in 2025-26, with no
               2023-24 detection within 60 m and < 0.12 hot frequency there
               in 2023-24

The firing test detects 75.6% of active reference kilns (sensitivity, from
firing_verify.py), so an active kiln is called 'stopped' 24.4% of the time.
Corrected stop rate:  c = (observed - 0.244) / 0.756.
That error is the same near schools and elsewhere, so H3's comparison of stop
rates is unaffected by it.

Output:
    data/kilns/kilns_change_32643.gpkg
    outputs/tables/kiln_change_summary.csv
"""

from pathlib import Path

import ee
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

import firing_verify as fv

ROOT = Path(__file__).resolve().parents[1]
THR, SENS, MATCH_M = 0.12, 0.756, 60
K = ROOT / "data" / "kilns"


def hot_image(start: str, end: str) -> ee.Image:
    def prep(img):
        qa = img.select("QA60")
        clear = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
        return img.normalizedDifference(["B12", "B11"]).gt(0).updateMask(clear).rename("hot")
    return (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterDate(start, end)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)).map(prep).mean().rename("hot_frac"))


def cached(name: str, img: ee.Image, g: gpd.GeoDataFrame) -> np.ndarray:
    """Sample once and keep the result on disk, so a crash does not cost the finished passes."""
    f = K / f"cache_change_{name}_{len(g)}.npy"
    if f.exists():
        print(f"    (cached {f.name})")
        return np.load(f)
    v = fv.sample(img, g)
    np.save(f, v)
    return v


def main() -> None:
    ee.Initialize(project="geosync-448701")
    img24, img26 = hot_image("2023-11-01", "2024-06-01"), hot_image("2025-11-01", "2026-06-01")

    a = gpd.read_file(K / "detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
    b = gpd.read_file(K / "detections_s2526_kiln_obb_ring_v1_best_filtered.gpkg")

    old = a[a.fires].copy().reset_index(drop=True)
    print("2023-24 firing kilns: sampling 2025-26 firing")
    old["hot26"] = cached("old26", img26, old)
    old["status"] = np.where(old.hot26 >= THR, "continuing", "stopped")

    print("2025-26 detections: sampling firing in both seasons")
    b["hot26"] = cached("b26", img26, b)
    cand = b[b.hot26 >= THR].copy().reset_index(drop=True)
    far = cKDTree(np.c_[a.geometry.x, a.geometry.y]).query(np.c_[cand.geometry.x, cand.geometry.y])[0] > MATCH_M
    cand = cand[far].reset_index(drop=True)
    cand["hot24"] = cached("cand24", img24, cand)
    new = cand[cand.hot24 < THR].assign(status="new")

    keep = ["status", "conf", "hot_frac", "hot26", "geometry"]
    allk = pd.concat([old.reindex(columns=keep), new.rename(columns={"hot24": "hot_frac"}).reindex(columns=keep)],
                     ignore_index=True)
    allk = gpd.GeoDataFrame(allk, crs=a.crs)
    allk.to_file(K / "kilns_change_32643.gpkg", driver="GPKG")

    n_old = len(old)
    obs_stop = (old.status == "stopped").mean()
    corr_stop = max((obs_stop - (1 - SENS)) / SENS, 0)
    s = pd.Series({
        "firing_kilns_2023_24": n_old,
        "continuing": int((old.status == "continuing").sum()),
        "stopped_observed": int((old.status == "stopped").sum()),
        "stop_rate_observed_pct": round(100 * obs_stop, 1),
        "stop_rate_corrected_pct": round(100 * corr_stop, 1),
        "new_firing_kilns_2025_26": len(new),
    })
    s.to_csv(ROOT / "outputs" / "tables" / "kiln_change_summary.csv", header=["value"])
    print(s.to_string())


if __name__ == "__main__":
    main()
