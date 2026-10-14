"""
Step 22 confound check: did the observing system change?
Sentinel-2C replaced Sentinel-2A in January 2025. If its SWIR response differs,
background hot frequency at non-kiln points would shift at that date and could
masquerade as kilns firing less (or stopping). Same monthly measurement as
monthly_firing.py, at the 1,000 random control points (firing_verify.controls).
Output: data/kilns/monthly_firing_controls.parquet, outputs/tables/monthly_firing_controls.csv
"""
import time
from pathlib import Path
import ee, geopandas as gpd, numpy as np, pandas as pd
import firing_verify as fv
from monthly_firing import month_image, MONTHS

ROOT = Path(__file__).resolve().parents[1]
K = ROOT / "data" / "kilns"
CACHE = K / "monthly_cache_controls"; CACHE.mkdir(exist_ok=True)


def main():
    ee.Initialize(project="geosync-448701"); ee.data.setDeadline(180_000)
    ncr = gpd.read_file(ROOT / "data/boundaries/ncr_4326.geojson").total_bounds
    roi = ee.Geometry.Rectangle(list(map(float, ncr)))
    det = gpd.read_file(K / "detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
    ctl = fv.controls(1000, np.c_[det.geometry.x, det.geometry.y]).to_crs(4326)
    fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([p.x, p.y]).buffer(fv.BUF), {"i": i}) for i, p in enumerate(ctl.geometry)])
    for m in MONTHS:
        f = CACHE / f"{m}.parquet"
        if f.exists(): continue
        for attempt in range(6):
            try:
                feats = month_image(m, roi).reduceRegions(fc, ee.Reducer.max(), scale=20).getInfo()["features"]; break
            except Exception as e:
                if attempt == 5: raise
                print("  retry", m, type(e).__name__, flush=True); time.sleep(20 * (attempt + 1))
        pd.DataFrame([{"i": x["properties"]["i"], "hot": x["properties"].get("hot"), "n": x["properties"].get("n")} for x in feats]).assign(month=str(m)).to_parquet(f)
        print(m, flush=True)
    a = pd.concat([pd.read_parquet(p) for p in sorted(CACHE.glob("*.parquet"))]); a.to_parquet(K / "monthly_firing_controls.parquet")
    s = a.groupby("month").agg(observed=("hot", lambda x: int(x.notna().sum())), median_clear=("n", "median"), mean_hot_share=("hot", "mean"))
    s.round(4).to_csv(ROOT / "outputs/tables/monthly_firing_controls.csv"); print(s.round(3).to_string())


if __name__ == "__main__":
    main()
