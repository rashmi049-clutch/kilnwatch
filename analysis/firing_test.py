"""
Phase 3 go/no-go - can Sentinel-2 see brick kilns firing?

Index: Normalized Hot-spot Index, NHI_SWIR = (B12 - B11) / (B12 + B11)
(Marchese et al. 2019, developed for volcanic and industrial hot spots).
Hot surfaces emit strongly in SWIR, and more at 2.2 um (B12) than 1.6 um
(B11); ordinary ground reflects the other way round, so NHI > 0 is rare
except over heat sources.

Test: 100 known NCR kilns (SentinelKilnDB, 2023-24) against 100 control points
at least 1.5 km from any known kiln, every clear Sentinel-2 scene of 2024.
Statistic per point per scene: maximum NHI within 40 m.

Expected if firing is visible:
  * kilns flag far more often than controls, and
  * kiln flags follow the firing season (roughly Nov-Jun) and collapse in
    the monsoon (Jul-Sep), when kilns are shut.
Either condition failing is a no-go, recorded as a result.

Output:
    outputs/tables/firing_test_obs.csv       one row per point per scene
    outputs/figures/05_firing_test.png
"""

from pathlib import Path

import ee
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UTM = "EPSG:32643"
N, SEED, BUF, MIN_SEP = 100, 7, 40, 1500


def sample_points() -> gpd.GeoDataFrame:
    k = gpd.read_file(ROOT / "data" / "kilns" / "kilndb_ncr_points_32643.gpkg")
    kilns = k.sample(N, random_state=SEED).assign(kind="kiln")[["kind", "cls", "geometry"]]
    ncr = gpd.read_file(ROOT / "data" / "boundaries" / "ncr_32643.gpkg").geometry.iloc[0]
    excl = k.buffer(MIN_SEP).union_all()
    rng = np.random.default_rng(SEED)
    minx, miny, maxx, maxy = ncr.bounds
    ctrl = []
    while len(ctrl) < N:
        p = gpd.points_from_xy(rng.uniform(minx, maxx, 200), rng.uniform(miny, maxy, 200), crs=UTM)
        for q in p:
            if q.within(ncr) and not q.within(excl):
                ctrl.append(q)
    c = gpd.GeoDataFrame({"kind": "control", "cls": "", "geometry": ctrl[:N]}, crs=UTM)
    pts = pd.concat([kilns, c], ignore_index=True)
    pts["pid"] = range(len(pts))
    return gpd.GeoDataFrame(pts, crs=UTM)


def run_ee(pts: gpd.GeoDataFrame) -> pd.DataFrame:
    ee.Initialize(project="geosync-448701")
    ll = pts.to_crs(4326)
    fc = ee.FeatureCollection([
        ee.Feature(ee.Geometry.Point([g.x, g.y]).buffer(BUF), {"pid": int(p), "kind": k})
        for g, p, k in zip(ll.geometry, ll.pid, ll.kind)])

    def prep(img):
        qa = img.select("QA60")
        clear = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
        nhi = img.normalizedDifference(["B12", "B11"]).rename("nhi")
        return nhi.updateMask(clear).set("date", img.date().format("YYYY-MM-dd"))

    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(fc.geometry()).filterDate("2024-01-01", "2025-01-01")
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)).map(prep))

    def per_image(img):
        r = img.reduceRegions(fc, ee.Reducer.max(), scale=20)
        return r.map(lambda f: f.set("date", img.get("date")))

    out = col.map(per_image).flatten().filter(ee.Filter.notNull(["max"]))
    rows = []
    # page through in chunks to stay under getInfo limits
    size = out.size().getInfo()
    lst = out.toList(size)
    for i in range(0, size, 4000):
        feats = ee.FeatureCollection(lst.slice(i, i + 4000)).getInfo()["features"]
        rows += [f["properties"] for f in feats]
    return pd.DataFrame(rows)


def main() -> None:
    pts = sample_points()
    obs = run_ee(pts).rename(columns={"max": "nhi"})
    obs["month"] = pd.to_datetime(obs.date).dt.month
    obs["hot"] = obs.nhi > 0
    obs.to_csv(ROOT / "outputs" / "tables" / "firing_test_obs.csv", index=False)

    m = obs.groupby(["kind", "month"]).hot.mean().unstack(0) * 100
    n = obs.groupby("kind").size()
    print("clear observations:", n.to_dict())
    print("share of observations flagged hot (%), by month:")
    print(m.round(1).to_string())
    season = obs.assign(s=np.where(obs.month.isin([7, 8, 9]), "monsoon", "dry"))
    print(season.groupby(["kind", "s"]).hot.mean().unstack().mul(100).round(1))
    ever = obs.groupby(["kind", "pid"]).hot.any().groupby("kind").mean() * 100
    print("points flagged at least once (%):", ever.round(0).to_dict())

    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=200)
    for kind, col in (("kiln", "#9c3f2a"), ("control", "#5d646b")):
        if kind in m:
            ax.plot(m.index, m[kind], marker="o", color=col, label=kind.capitalize() + "s")
    ax.axvspan(6.5, 9.5, color="#dfe9f3", zorder=0, label="Monsoon (kilns shut)")
    ax.set_xticks(range(1, 13), ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.set_ylabel("Observations flagged hot (%)")
    ax.set_title("Sentinel-2 hot-spot flags at known kilns vs controls, NCR 2024", loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(ROOT / "outputs" / "figures" / "05_firing_test.png")


if __name__ == "__main__":
    main()
