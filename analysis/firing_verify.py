"""
Step 12 (replacement) - verify detections by whether they fire.

Visual review proved impractical: at basemap resolution a non-specialist
cannot reliably tell a kiln from a brick-coloured field. The hot-spot signal
validated in the Phase 3 go/no-go test (kilns flagged in 33% of dry-season
scenes vs 4% for random points) is used instead, as an objective check that
needs no interpretation and covers every detection.

Firing-season hot frequency per 10 m pixel:
    hot_frac = (# clear scenes with NHI_SWIR > 0) / (# clear scenes)
    Sentinel-2 SR, 1 Nov 2023 - 1 Jun 2024, cloud < 30%, QA60 masked.
Per point: maximum hot_frac within 40 m.

Calibration groups:
    reference  - 4,114 hand-labelled NCR kilns (SentinelKilnDB)
    control    - 1,000 random NCR points >= 1.5 km from any reference kiln
                 and from any detection
Threshold: chosen from the data as the hot_frac that best separates the
two groups (Youden's J on the ROC), then applied to every detection.

Independent spot check: OpenStreetMap man_made=kiln features (179 in NCR).

Output:
    adds hot_frac to detections_*_filtered.gpkg
    outputs/tables/firing_verify_summary.csv
    outputs/figures/06_firing_verify.png
"""

import time
from pathlib import Path

import ee
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
UTM = "EPSG:32643"
BUF, CHUNK, SEED = 40, 2500, 21
DET = ROOT / "data" / "kilns" / "detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg"
RAW = ROOT / "data" / "kilns" / "detections_s2324_kiln_obb_ring_v1_best.gpkg"


def hot_image() -> ee.Image:
    def prep(img):
        qa = img.select("QA60")
        clear = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
        hot = img.normalizedDifference(["B12", "B11"]).gt(0)
        return hot.updateMask(clear).rename("hot")

    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterDate("2023-11-01", "2024-06-01")
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)).map(prep))
    return col.mean().rename("hot_frac")   # mean of 0/1 over clear scenes = share hot


def sample(img: ee.Image, g: gpd.GeoDataFrame) -> np.ndarray:
    ll = g.to_crs(4326).reset_index(drop=True)
    out = np.full(len(ll), np.nan)
    for s in range(0, len(ll), CHUNK):
        sub = ll.iloc[s:s + CHUNK]
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([p.x, p.y]).buffer(BUF), {"i": int(i)})
                                   for i, p in zip(sub.index, sub.geometry)])
        for attempt in range(8):  # survive network drops (Wi-Fi, sleep) instead of losing the run
            try:
                feats = img.reduceRegions(fc, ee.Reducer.max(), scale=20).getInfo()["features"]
                break
            except Exception as e:
                if attempt == 7:
                    raise
                print(f"    retry {attempt + 1} after: {type(e).__name__}", flush=True)
                time.sleep(30 * (attempt + 1))
        for f in feats:
            out[f["properties"]["i"]] = f["properties"].get("max", np.nan)
        print(f"    {min(s + CHUNK, len(ll))}/{len(ll)}", flush=True)
    return out


def controls(n: int, avoid: np.ndarray) -> gpd.GeoDataFrame:
    ncr = gpd.read_file(ROOT / "data" / "boundaries" / "ncr_32643.gpkg").geometry.iloc[0]
    tree = cKDTree(avoid)
    rng = np.random.default_rng(SEED)
    minx, miny, maxx, maxy = ncr.bounds
    pts = []
    while len(pts) < n:
        xy = np.c_[rng.uniform(minx, maxx, 2000), rng.uniform(miny, maxy, 2000)]
        ok = tree.query(xy)[0] >= 1500
        for x, y in xy[ok]:
            p = gpd.points_from_xy([x], [y])[0]
            if p.within(ncr):
                pts.append(p)
    return gpd.GeoDataFrame(geometry=pts[:n], crs=UTM)


def main() -> None:
    ee.Initialize(project="geosync-448701")
    img = hot_image()
    det = gpd.read_file(DET)
    raw = gpd.read_file(RAW)
    ref = gpd.read_file(ROOT / "data" / "kilns" / "kilndb_ncr_points_32643.gpkg")
    osm = gpd.read_file(ROOT / "data" / "kilns" / "osm_kilns_ncr_32643.gpkg")
    avoid = np.r_[np.c_[ref.geometry.x, ref.geometry.y], np.c_[raw.geometry.x, raw.geometry.y]]
    ctl = controls(1000, avoid)

    print("sampling hot frequency:")
    for name, g in (("reference", ref), ("control", ctl), ("detections", det)):
        print(f"  {name}")
        g["hot_frac"] = sample(img, g)
    det.to_file(DET, driver="GPKG")

    # threshold from the data: Youden's J between reference kilns and controls
    r, c = ref.hot_frac.dropna().to_numpy(), ctl.hot_frac.dropna().to_numpy()
    ts = np.round(np.arange(0.0, 0.61, 0.01), 2)
    J = [(r >= t).mean() - (c >= t).mean() for t in ts]
    thr = float(ts[int(np.argmax(J))])
    tpr, fpr = (r >= thr).mean(), (c >= thr).mean()

    det_fire = (det.hot_frac >= thr).mean()
    # what share of detections would fire if they were all real kilns / all non-kilns -> implied precision
    implied_precision = (det_fire - fpr) / (tpr - fpr)
    osm_near = cKDTree(np.c_[det.geometry.x, det.geometry.y]).query(np.c_[osm.geometry.x, osm.geometry.y])[0] <= 100

    summary = pd.Series({
        "threshold_hot_frac": thr,
        "reference_kilns_firing_pct": 100 * tpr,
        "control_points_firing_pct": 100 * fpr,
        "detections_firing_pct": 100 * det_fire,
        "implied_precision_of_filtered_map": implied_precision,
        "osm_kilns_found_within_100m_pct": 100 * osm_near.mean(),
        "osm_kilns_n": len(osm),
        "median_hot_frac_reference": float(np.median(r)),
        "median_hot_frac_control": float(np.median(c)),
        "median_hot_frac_detections": float(det.hot_frac.median()),
    }).round(3)
    summary.to_csv(ROOT / "outputs" / "tables" / "firing_verify_summary.csv", header=["value"])
    print(summary.to_string())

    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=200)
    bins = np.linspace(0, 0.8, 41)
    for vals, lab, col in ((c, "Random points", "#5d646b"), (r, "Hand-labelled kilns", "#9c3f2a"),
                           (det.hot_frac.dropna().to_numpy(), "Our detections", "#2d5c88")):
        ax.hist(vals, bins=bins, density=True, histtype="step", lw=1.6, color=col, label=lab)
    ax.axvline(thr, color="black", ls="--", lw=1)
    ax.text(thr + 0.01, ax.get_ylim()[1] * 0.9, f"threshold {thr:.2f}", fontsize=8)
    ax.set_xlabel("Share of clear firing-season scenes flagged hot (max within 40 m)")
    ax.set_ylabel("Density")
    ax.set_title("Do detections fire like kilns? Nov 2023 - May 2024", loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(ROOT / "outputs" / "figures" / "06_firing_verify.png")


if __name__ == "__main__":
    main()
