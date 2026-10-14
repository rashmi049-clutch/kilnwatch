"""
Step 23 confound check: is the emergency-day drop just seasonal timing?
Emergency days cluster in Nov-Jan; ordinary days include more February, when
kilns fire more. So compare emergency vs ordinary days WITHIN the same calendar
month (Dec 2024, Jan 2025, Feb 2025, Nov 2025, Dec 2025, Jan 2026), then average.
Output: outputs/tables/grap_firing_bymonth.csv
"""
from pathlib import Path
import ee, geopandas as gpd, numpy as np, pandas as pd
import firing_verify as fv
from grap_firing import ban_dates, sample, START, END

ROOT = Path(__file__).resolve().parents[1]
K = ROOT / "data" / "kilns"
MONTHS = ["2024-12", "2025-01", "2025-02", "2025-11", "2025-12", "2026-01"]


def main():
    ee.Initialize(project="geosync-448701")
    ncr = gpd.read_file(ROOT / "data/boundaries/ncr_4326.geojson").total_bounds
    def prep(img):
        qa = img.select("QA60")
        clear = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
        return (img.normalizedDifference(["B12", "B11"]).gt(0).updateMask(clear).rename("hot")
                .copyProperties(img, ["system:time_start"])   # keep the date for filterDate
                .set("day", ee.Date(img.get("system:time_start")).format("YYYY-MM-dd")))
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterDate(START, END)
           .filterBounds(ee.Geometry.Rectangle(list(map(float, ncr))))
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)).map(prep))
    bans = ee.List(ban_dates())
    bands = []
    for m in MONTHS:
        a = pd.Timestamp(f"{m}-01"); b = a + pd.offsets.MonthBegin(1)
        cm = col.filterDate(a.strftime("%Y-%m-%d"), b.strftime("%Y-%m-%d"))
        on, off = cm.filter(ee.Filter.inList("day", bans)), cm.filter(ee.Filter.inList("day", bans).Not())
        print(m, "emergency scenes", on.size().getInfo(), "ordinary", off.size().getInfo())
        t = m.replace("-", "")
        bands += [on.mean().rename(f"on_{t}"), off.mean().rename(f"off_{t}")]
    img = ee.Image.cat(bands)
    det = gpd.read_file(K / "detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
    kil = det[det.kiln_final].reset_index(drop=True)
    ctl = fv.controls(1000, np.c_[det.geometry.x, det.geometry.y])
    f = K / "grap_firing_bymonth.parquet"
    if f.exists():
        d = pd.read_parquet(f)
    else:
        print("kilns"); a = sample(img, kil).assign(group="kiln")
        print("controls"); b = sample(img, ctl).assign(group="control")
        d = pd.concat([a, b], ignore_index=True); d.to_parquet(f)
    rows = []
    for m in MONTHS:
        t = m.replace("-", "")
        if f"on_{t}" not in d or f"off_{t}" not in d: continue
        for g, x in d.groupby("group"):
            x = x[[f"on_{t}", f"off_{t}"]].dropna()
            rows.append({"month": m, "group": g, "n": len(x), "emergency_pct": 100 * x.iloc[:, 0].mean(),
                         "ordinary_pct": 100 * x.iloc[:, 1].mean()})
    r = pd.DataFrame(rows); r["diff_pp"] = r.emergency_pct - r.ordinary_pct
    w = r.pivot(index="month", columns="group", values="diff_pp")
    w["did_pp"] = w.kiln - w.control
    n = r[r.group == "kiln"].set_index("month").n
    pooled = np.average(w.did_pp, weights=n.reindex(w.index))
    r.round(2).to_csv(ROOT / "outputs/tables/grap_firing_bymonth.csv", index=False)
    print(r.round(1).to_string(index=False)); print(w.round(2).to_string())
    print(f"\nwithin-month DiD, weighted by kilns observed: {pooled:.2f} pp")


if __name__ == "__main__":
    main()
