"""
Step 23 - Do brick kilns keep firing on GRAP Stage III/IV (emergency) days?

The Dec 2024 and Nov 2025 GRAP schedules do not close brick kilns at Stage III
or IV. This measures whether kilns in fact fire on those days.

Period: 13 Dec 2024 (Dec 2024 schedule in force) to 28 Feb 2026, restricted to
November-February so emergency and ordinary days come from the same season.
For each point: share of clear Sentinel-2 scenes (cloud < 30%, QA60 masked)
with NHI_SWIR > 0, on emergency days and on ordinary days (max within 40 m).
Haze on emergency days nudges the index up everywhere, so the effect is netted
against 1,000 random control points (difference-in-differences).
Kilns: cleaned firing-verified layer (kiln_final).

Output: data/kilns/grap_firing.parquet, outputs/tables/grap_firing_summary.csv
"""
import time
from pathlib import Path
import ee, geopandas as gpd, numpy as np, pandas as pd
from scipy.stats import wilcoxon
import firing_verify as fv

ROOT = Path(__file__).resolve().parents[1]
K = ROOT / "data" / "kilns"
START, END = "2024-12-13", "2026-03-01"


def ban_dates() -> list[str]:
    w = pd.read_csv(ROOT / "data/grap/grap_stage3_windows.csv", parse_dates=["start", "end"])
    days = pd.DatetimeIndex(sorted({d for s, e in zip(w.start, w.end) for d in pd.date_range(s, e)}))
    return [d.strftime("%Y-%m-%d") for d in days if START <= d.strftime("%Y-%m-%d") < END]


def images():
    def prep(img):
        qa = img.select("QA60")
        clear = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
        hot = img.normalizedDifference(["B12", "B11"]).gt(0).updateMask(clear)
        day = ee.Date(img.get("system:time_start")).format("YYYY-MM-dd")
        return hot.rename("hot").set("day", day)
    ncr = gpd.read_file(ROOT / "data/boundaries/ncr_4326.geojson").total_bounds
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterDate(START, END)
           .filterBounds(ee.Geometry.Rectangle(list(map(float, ncr))))   # NCR only
           .filter(ee.Filter.calendarRange(11, 2, "month"))
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)).map(prep))
    bans = ee.List(ban_dates())
    on = col.filter(ee.Filter.inList("day", bans))
    off = col.filter(ee.Filter.inList("day", bans).Not())
    print("scenes: emergency", on.size().getInfo(), " ordinary", off.size().getInfo(),
          " distinct emergency dates", len(set(on.aggregate_array("day").getInfo())))
    return (on.mean().rename("hot_ban").addBands(on.count().rename("n_ban"))
            .addBands(off.mean().rename("hot_off")).addBands(off.count().rename("n_off")))


def sample(img, g, chunk=1500):
    ll = g.to_crs(4326).reset_index(drop=True)
    rows = []
    for s in range(0, len(ll), chunk):
        sub = ll.iloc[s:s + chunk]
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([p.x, p.y]).buffer(fv.BUF), {"i": int(i)})
                                   for i, p in zip(sub.index, sub.geometry)])
        for attempt in range(8):
            try:
                feats = img.reduceRegions(fc, ee.Reducer.max(), scale=20).getInfo()["features"]
                break
            except Exception as e:
                if attempt == 7: raise
                print("    retry", attempt + 1, type(e).__name__, flush=True); time.sleep(30 * (attempt + 1))
        rows += [f["properties"] for f in feats]
        print(f"    {min(s + chunk, len(ll))}/{len(ll)}", flush=True)
    return pd.DataFrame(rows).set_index("i").sort_index()


def main():
    ee.Initialize(project="geosync-448701")
    img = images()
    det = gpd.read_file(K / "detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
    kil = det[det.kiln_final].reset_index(drop=True)
    ctl = fv.controls(1000, np.c_[det.geometry.x, det.geometry.y])
    f = K / "grap_firing.parquet"
    if f.exists():
        d = pd.read_parquet(f)
    else:
        print("kilns"); a = sample(img, kil).assign(group="kiln", x=kil.geometry.x, y=kil.geometry.y)
        print("controls"); b = sample(img, ctl).assign(group="control", x=ctl.geometry.x, y=ctl.geometry.y)
        d = pd.concat([a, b], ignore_index=True); d.to_parquet(f)

    d = d[(d.n_ban >= 1) & (d.n_off >= 3)].copy()
    d["diff"] = d.hot_ban - d.hot_off
    out = {}
    for g, x in d.groupby("group"):
        out[f"{g}_n"] = len(x)
        out[f"{g}_hot_on_emergency_days_pct"] = round(100 * x.hot_ban.mean(), 1)
        out[f"{g}_hot_on_ordinary_days_pct"] = round(100 * x.hot_off.mean(), 1)
        out[f"{g}_diff_pp"] = round(100 * x["diff"].mean(), 2)
        out[f"{g}_wilcoxon_p"] = float(wilcoxon(x["diff"]).pvalue)
    k, c = d[d.group == "kiln"]["diff"], d[d.group == "control"]["diff"]
    did = k.mean() - c.mean()
    rng = np.random.default_rng(1)
    boot = [rng.choice(k.values, len(k)).mean() - rng.choice(c.values, len(c)).mean() for _ in range(2000)]
    out["did_pp"] = round(100 * did, 2)
    out["did_ci_low_pp"], out["did_ci_high_pp"] = [round(100 * v, 2) for v in np.percentile(boot, [2.5, 97.5])]
    kk = d[d.group == "kiln"]
    out["kilns_hot_on_at_least_one_emergency_scene_pct"] = round(100 * (kk.hot_ban > 0).mean(), 1)
    out["kiln_median_emergency_scenes"] = float(kk.n_ban.median())
    s = pd.Series(out); s.to_csv(ROOT / "outputs/tables/grap_firing_summary.csv", header=["value"])
    print(s.to_string())


if __name__ == "__main__":
    main()
