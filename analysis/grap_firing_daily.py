"""
Step 23, corrected design: the DAY is the unit of analysis.

Why: all kilns under one Sentinel-2 pass share that day's atmosphere and viewing
conditions, so per-kiln comparisons are pseudo-replicated (effective n = number
of days, not kilns). The first per-kiln bootstrap CI (-8.8 to -7.6 pp) was
therefore far too narrow and is withdrawn; month-by-month per-kiln results swung
from -45 to +32 pp.

For each day with imagery (13 Dec 2024 - 28 Feb 2026, Nov-Feb only):
    kiln_hot = share of observed (clear) kilns with NHI_SWIR > 0 (max in 40 m)
    ctl_hot  = same for 1,000 random control points
    net      = kiln_hot - ctl_hot
Days with < 200 observed kilns are dropped. Emergency vs ordinary days are
compared within calendar month (month fixed effects via demeaning), with a
bootstrap of days within month (CI) and a within-month permutation test (p).
Output: data/kilns/grap_daily.parquet, outputs/tables/grap_firing_daily_summary.csv
"""
import time
from pathlib import Path
import ee, geopandas as gpd, numpy as np, pandas as pd
import firing_verify as fv
from grap_firing import ban_dates, START, END

ROOT = Path(__file__).resolve().parents[1]
K = ROOT / "data" / "kilns"


def fc(g, grp):
    ll = g.to_crs(4326)
    return ee.FeatureCollection([ee.Feature(ee.Geometry.Point([p.x, p.y]).buffer(fv.BUF), {"g": grp})
                                 for p in ll.geometry])


def main():
    ee.Initialize(project="geosync-448701")
    ee.data.setDeadline(120_000)   # a hung request now fails after 2 min and is retried
    ncr = gpd.read_file(ROOT / "data/boundaries/ncr_4326.geojson").total_bounds
    roi = ee.Geometry.Rectangle(list(map(float, ncr)))
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterDate(START, END).filterBounds(roi)
          .filter(ee.Filter.calendarRange(11, 2, "month")).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)))
    days = sorted(set(s2.aggregate_array("system:time_start").map(
        lambda t: ee.Date(t).format("YYYY-MM-dd")).getInfo()))
    print("days with imagery:", len(days))

    det = gpd.read_file(K / "detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
    kil = det[det.kiln_final]
    ctl = fv.controls(1000, np.c_[det.geometry.x, det.geometry.y])
    pts = fc(kil, "kiln").merge(fc(ctl, "control"))

    def hot_day(d):
        d = ee.Date(d)
        def prep(img):
            qa = img.select("QA60")
            clear = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
            return img.normalizedDifference(["B12", "B11"]).gt(0).updateMask(clear).rename("hot")
        return s2.filterDate(d, d.advance(1, "day")).map(prep).max()

    f = K / "grap_daily.parquet"
    done = pd.read_parquet(f) if f.exists() else pd.DataFrame()
    rows = done.to_dict("records")
    for day in days:
        if any(r["day"] == day for r in rows):
            continue
        for attempt in range(6):
            try:
                red = hot_day(day).reduceRegions(pts, ee.Reducer.max(), scale=20)
                stats = {}
                for g in ("kiln", "control"):
                    sub = red.filter(ee.Filter.eq("g", g)).filter(ee.Filter.notNull(["max"]))
                    stats[g] = ee.Dictionary({"n": sub.size(), "hot": sub.aggregate_mean("max")})
                v = ee.Dictionary(stats).getInfo()
                break
            except Exception as e:
                if attempt == 5: raise
                print("  retry", day, type(e).__name__, flush=True); time.sleep(20 * (attempt + 1))
        rows.append({"day": day, "kiln_n": v["kiln"]["n"], "kiln_hot": v["kiln"]["hot"],
                     "ctl_n": v["control"]["n"], "ctl_hot": v["control"]["hot"]})
        pd.DataFrame(rows).to_parquet(f)
        print(day, v["kiln"]["n"], round(v["kiln"]["hot"] or 0, 3), flush=True)

    d = pd.DataFrame(rows)
    d = d[(d.kiln_n >= 200) & (d.ctl_n >= 50)].copy()
    bans = set(ban_dates())
    d["emergency"] = d.day.isin(bans).astype(int)
    d["month"] = d.day.str[:7]
    d["net"] = 100 * (d.kiln_hot - d.ctl_hot)
    d = d[d.groupby("month").emergency.transform(lambda s: s.nunique() == 2)]   # months with both kinds

    # month fixed effects by within-month demeaning (no statsmodels needed)
    def effect(x):
        e = x.emergency - x.groupby("month").emergency.transform("mean")
        y = x.net - x.groupby("month").net.transform("mean")
        return float((e * y).sum() / (e * e).sum())
    b = effect(d)
    rng = np.random.default_rng(3)
    boot = []   # resample days within month
    for _ in range(5000):
        idx = np.concatenate([rng.choice(ix, len(ix)) for ix in d.groupby("month").indices.values()])
        bb = d.iloc[idx]
        if bb.groupby("month").emergency.nunique().min() == 2:
            boot.append(effect(bb))
    lo, hi = np.percentile(boot, [2.5, 97.5])
    perm = []
    for _ in range(5000):
        dd = d.copy(); dd["emergency"] = dd.groupby("month").emergency.transform(lambda s: rng.permutation(s.values))
        perm.append(effect(dd))
    p_perm = float((np.abs(perm) >= abs(b)).mean())
    p = p_perm
    s = pd.Series({"days_used": len(d), "emergency_days": int(d.emergency.sum()), "ordinary_days": int((1 - d.emergency).sum()),
                   "net_firing_emergency_mean_pp": round(d[d.emergency == 1].net.mean(), 2),
                   "net_firing_ordinary_mean_pp": round(d[d.emergency == 0].net.mean(), 2),
                   "effect_within_month_pp": round(b, 2), "ci_low_pp": round(lo, 2), "ci_high_pp": round(hi, 2),
                   "p_permutation": round(p_perm, 4)})
    s.to_csv(ROOT / "outputs/tables/grap_firing_daily_summary.csv", header=["value"])
    print(d.groupby(["month", "emergency"]).net.agg(["size", "mean"]).round(1).to_string())
    print(s.to_string())


if __name__ == "__main__":
    main()
