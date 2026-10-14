"""
Step 7 - Fetch Sentinel-2 RGB composites for the whole NCR, two seasons.

Grid: 1024 x 1024 px tiles at 10 m (10.24 km) in EPSG:32643, aligned to a
10 m grid, kept only where they touch the NCR. Every tile is requested with
an explicit crs_transform, so pixels line up exactly across seasons - a kiln
is at the same pixel in both years.

Composite: COPERNICUS/S2_SR_HARMONIZED, scenes with < 20% cloud, QA60 opaque
and cirrus bits masked, per-pixel median over the season. Same bands and
cloud mask as SentinelKilnDB; median rather than their best-single-scene
pick, because a fixed rule over two seasons matters more here than matching
one date. The effect on accuracy is tested (step 11), not assumed.

Seasons (same months both years, so crop phenology and winter haze are held
constant):
    s2324 = 2023-11-01 .. 2024-03-01
    s2526 = 2025-11-01 .. 2026-03-01

Usage:
    python analysis/fetch_s2_tiles.py grid               # build tile grid
    python analysis/fetch_s2_tiles.py fetch s2324 [N]    # fetch (N = test limit)
Resumable: tiles already on disk are skipped.
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import ee
import geopandas as gpd
import numpy as np
import requests
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "s2"
GRID = OUT / "tile_grid_32643.gpkg"
UTM = "EPSG:32643"
TILE_PX, RES = 1024, 10
TILE_M = TILE_PX * RES
SEASONS = {"s2324": ("2023-11-01", "2024-03-01"), "s2526": ("2025-11-01", "2026-03-01")}
PROJECT = "geosync-448701"
WORKERS = 4


def build_grid() -> None:
    ncr = gpd.read_file(ROOT / "data" / "boundaries" / "ncr_32643.gpkg").geometry.iloc[0]
    minx, miny, maxx, maxy = ncr.bounds
    x0 = np.floor(minx / TILE_M) * TILE_M
    y0 = np.floor(miny / TILE_M) * TILE_M
    rows = []
    for x in np.arange(x0, maxx, TILE_M):
        for y in np.arange(y0, maxy, TILE_M):
            b = box(x, y, x + TILE_M, y + TILE_M)
            if b.intersects(ncr):
                rows.append({"tile_id": f"{int(x)}_{int(y + TILE_M)}", "x_ul": x, "y_ul": y + TILE_M, "geometry": b})
    g = gpd.GeoDataFrame(rows, crs=UTM)
    OUT.mkdir(parents=True, exist_ok=True)
    g.to_file(GRID, driver="GPKG")
    print(f"{len(g)} tiles of {TILE_M / 1000:.2f} km -> {GRID.name}")


def composite(season: str) -> ee.Image:
    start, end = SEASONS[season]

    def mask(img):
        qa = img.select("QA60")
        clear = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
        return img.updateMask(clear)

    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterDate(start, end)
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
           .map(mask))
    return col.select(["B4", "B3", "B2"]).median().toUint16()


def fetch_one(img: ee.Image, row, season: str) -> str:
    path = OUT / season / f"{row.tile_id}.tif"
    if path.exists() and path.stat().st_size > 10_000:
        return "skip"
    url = img.getDownloadURL({
        "format": "GEO_TIFF",
        "crs": UTM,
        "crs_transform": [RES, 0, float(row.x_ul), 0, -RES, float(row.y_ul)],
        "dimensions": f"{TILE_PX}x{TILE_PX}",
    })
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=300)
            if r.ok and r.content[:2] in (b"II", b"MM"):
                path.write_bytes(r.content)
                return "ok"
        except requests.RequestException:
            pass
        time.sleep(5 * (attempt + 1))
    return "fail"


def fetch(season: str, limit: int | None) -> None:
    ee.Initialize(project=PROJECT)
    g = gpd.read_file(GRID)
    if limit:
        # test on tiles near the NCR centre, where kilns are dense
        c = g.geometry.union_all().centroid
        g = g.assign(d=g.distance(c)).nsmallest(limit, "d")
    (OUT / season).mkdir(parents=True, exist_ok=True)
    img = composite(season)
    counts = {"ok": 0, "skip": 0, "fail": 0}
    t0 = time.time()
    with ThreadPoolExecutor(WORKERS) as pool:
        futs = {pool.submit(fetch_one, img, r, season): r.tile_id for r in g.itertuples()}
        for i, f in enumerate(as_completed(futs), 1):
            counts[f.result()] += 1
            if i % 25 == 0 or i == len(futs):
                print(f"  {season}: {i}/{len(futs)} {counts}  {time.time() - t0:.0f}s", flush=True)
    failed = [futs[f] for f in futs if f.result() == "fail"]
    if failed:
        print("FAILED:", failed)


if __name__ == "__main__":
    if sys.argv[1] == "grid":
        build_grid()
    else:
        fetch(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else None)
