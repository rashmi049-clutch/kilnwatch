"""
Rashmi's own Google Maps scrape of NCR schools -> a LOCAL-ONLY comparison layer for the dashboard.

Google Maps content may not be republished, so this layer never leaves her PC:
  * written to dashboard/public/local/ (git-ignored)
  * stripped from the static export by dashboard/scripts/publish.mjs, so the live site never has it
  * not used in any count or in the report's numbers

Input : C:/projects/ncr-schools/google-maps-scraper/ncr/ncr_schools_final.gpkg (layer "places", EPSG:4326)
Output: dashboard/public/local/google_schools.json  [[lat, lon, title, category, class, reviews], ...]
"""
import json
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(r"C:\projects\ncr-schools\google-maps-scraper\ncr\ncr_schools_final.gpkg")
OUT = ROOT / "dashboard/public/local"
OUT.mkdir(parents=True, exist_ok=True)

g = gpd.read_file(SRC, layer="places").to_crs(4326)
print(f"Google Maps school places: {len(g)}")
clean = lambda v: "" if v is None or v != v else str(v)
rows = [[round(p.y, 5), round(p.x, 5), clean(t), clean(c), clean(k), int(r) if r == r and r is not None else 0]
        for p, t, c, k, r in zip(g.geometry, g.title, g.category, g["class"], g.review_count)]
(OUT / "google_schools.json").write_text(json.dumps(rows, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
print(f"wrote {OUT / 'google_schools.json'} ({(OUT / 'google_schools.json').stat().st_size / 1e6:.1f} MB)")
