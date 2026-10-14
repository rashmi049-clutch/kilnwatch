"""
Phase 3 confound check - is the hot-spot signal fire, or brick material?

The seasonal collapse in July-September fits kilns shutting down, but also
fits wet ground changing SWIR reflectance. A zigzag kiln fires progressively
around its trench, so the burning zone moves around the ~100 m kiln loop from
day to day; fired brick or clay does not move.

Test: for the 30 most frequently flagged kilns, find the position of the
hottest 20 m pixel (max NHI) within 80 m of the kiln centre on every
flagged date. Measure how far that position moves between dates.

Reading:
  * material  -> the same pixel wins every time (spread ~ 0-10 m, one pixel)
  * fire      -> the winning pixel wanders around the kiln (spread tens of m,
                 many distinct pixels)
Positional noise floor: Sentinel-2 multi-date registration is ~10 m, i.e.
half a 20 m pixel.

Output:
    outputs/tables/firing_motion.csv
"""

from pathlib import Path

import ee
import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UTM = "EPSG:32643"
N_KILNS, BUF = 30, 80


def main() -> None:
    obs = pd.read_csv(ROOT / "outputs" / "tables" / "firing_test_obs.csv")
    top = (obs[obs.kind == "kiln"].groupby("pid").hot.sum()
           .sort_values(ascending=False).head(N_KILNS).index.tolist())

    # rebuild the same sample to recover coordinates for these pids
    import firing_test as ft
    pts = ft.sample_points()
    sel = pts[pts.pid.isin(top)].to_crs(4326)

    ee.Initialize(project="geosync-448701")
    rows = []
    for r in sel.itertuples():
        region = ee.Geometry.Point([r.geometry.x, r.geometry.y]).buffer(BUF)
        dates = obs[(obs.pid == r.pid) & obs.hot].date.unique().tolist()

        def locate(img):
            nhi = img.normalizedDifference(["B12", "B11"]).rename("nhi")
            stack = nhi.addBands(ee.Image.pixelCoordinates(ee.Projection(UTM)))
            m = stack.reduceRegion(ee.Reducer.max(3), region, scale=20, crs=UTM)
            return ee.Feature(None, m).set("date", img.date().format("YYYY-MM-dd"))

        col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
               .filterBounds(region).filterDate("2024-01-01", "2025-01-01")
               .filter(ee.Filter.inList("system:index", ee.List([])).Not()))
        col = col.filter(ee.Filter.calendarRange(1, 12, "month"))
        feats = ee.FeatureCollection(col.map(locate)).filter(ee.Filter.inList("date", dates)).getInfo()["features"]
        for f in feats:
            p = f["properties"]
            if p.get("max") is not None:
                rows.append({"pid": r.pid, "date": p["date"], "nhi": p["max"], "x": p["max1"], "y": p["max2"]})

    d = pd.DataFrame(rows).drop_duplicates(["pid", "date"])
    d.to_csv(ROOT / "outputs" / "tables" / "firing_motion.csv", index=False)

    def spread(g):
        xy = g[["x", "y"]].to_numpy()
        c = xy.mean(0)
        return pd.Series({
            "dates": len(g),
            "distinct_pixels": len({(round(a), round(b)) for a, b in xy}),
            "rms_spread_m": float(np.sqrt(((xy - c) ** 2).sum(1).mean())),
            "max_jump_m": float(np.max(np.hypot(*(xy[:, None, :] - xy[None, :, :]).transpose(2, 0, 1)))),
        })

    s = d.groupby("pid").apply(spread)
    print(s.describe().round(1).loc[["count", "mean", "50%", "min", "max"]].to_string())
    print("kilns whose hot spot never moves (1 distinct pixel):",
          int((s.distinct_pixels == 1).sum()), "of", len(s))


if __name__ == "__main__":
    main()
