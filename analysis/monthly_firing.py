"""
Step 22 - monthly firing record for every kiln, Nov 2023 - Jun 2026.

For each calendar month: hot share = (clear Sentinel-2 scenes with NHI_SWIR > 0)
/ (clear scenes), max within 40 m, per kiln (cleaned layer, kiln_final), plus the
number of clear scenes (so noisy monsoon months can be flagged). One Earth Engine
reduction per month; each month is cached, so the run resumes after a drop.
Output: data/kilns/monthly_firing.parquet (kiln x month), outputs/tables/monthly_firing_ncr.csv
"""
import time
from pathlib import Path
import ee, geopandas as gpd, numpy as np, pandas as pd
import firing_verify as fv

ROOT = Path(__file__).resolve().parents[1]
K = ROOT / "data" / "kilns"
CACHE = K / "monthly_cache"; CACHE.mkdir(exist_ok=True)
MONTHS = pd.period_range("2023-11", "2026-06", freq="M")


def month_image(m, roi):
    def prep(img):
        qa = img.select("QA60")
        clear = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
        hot = img.normalizedDifference(["B12", "B11"]).gt(0).updateMask(clear)
        return hot.rename("hot").addBands(clear.selfMask().rename("n"))
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(roi)
           .filterDate(str(m.start_time.date()), str((m + 1).start_time.date()))
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 60)).map(prep))
    return col.select("hot").mean().addBands(col.select("n").count())


def main():
    ee.Initialize(project="geosync-448701")
    ee.data.setDeadline(180_000)
    ncr = gpd.read_file(ROOT / "data/boundaries/ncr_4326.geojson").total_bounds
    roi = ee.Geometry.Rectangle(list(map(float, ncr)))
    det = gpd.read_file(K / "detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
    kil = det[det.kiln_final]
    ll = kil.to_crs(4326)
    fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([p.x, p.y]).buffer(fv.BUF), {"i": int(i)})
                               for i, p in zip(kil.index, ll.geometry)])
    for m in MONTHS:
        f = CACHE / f"{m}.parquet"
        if f.exists():
            continue
        for attempt in range(6):
            try:
                feats = month_image(m, roi).reduceRegions(fc, ee.Reducer.max(), scale=20).getInfo()["features"]
                break
            except Exception as e:
                if attempt == 5: raise
                print("  retry", m, type(e).__name__, flush=True); time.sleep(20 * (attempt + 1))
        rows = [{"det_index": x["properties"]["i"], "hot": x["properties"].get("hot"), "n": x["properties"].get("n")} for x in feats]
        pd.DataFrame(rows).assign(month=str(m)).to_parquet(f)
        d = pd.DataFrame(rows)
        print(m, "kilns observed", int(d.hot.notna().sum()), "median clear scenes", d.n.median(), "share hot>=0.12", round((d.hot >= 0.12).mean(), 3), flush=True)

    allm = pd.concat([pd.read_parquet(p) for p in sorted(CACHE.glob("*.parquet"))])
    allm.to_parquet(K / "monthly_firing.parquet")
    ncr_m = allm.groupby("month").agg(kilns_observed=("hot", lambda s: int(s.notna().sum())),
                                      median_clear_scenes=("n", "median"),
                                      mean_hot_share=("hot", "mean"),
                                      share_kilns_firing=("hot", lambda s: (s >= 0.12).sum() / max(s.notna().sum(), 1)))
    ncr_m.round(3).to_csv(ROOT / "outputs/tables/monthly_firing_ncr.csv")
    print(ncr_m.round(3).to_string())


if __name__ == "__main__":
    main()
