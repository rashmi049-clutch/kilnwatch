"""
Rashmi's own Google Maps scrape of NCR schools -> a LOCAL-ONLY comparison layer for the dashboard.

Google Maps content may not be republished, so this layer never leaves her PC:
  * written to dashboard/public/local/ (git-ignored)
  * stripped from the static export by dashboard/scripts/publish.mjs, so the live site never has it
  * not used in any count or in the report's numbers
  (signed-in editors can get the same file from the private Supabase bucket "private-layer")

Input : C:/projects/ncr-schools/google-maps-scraper/ncr/ncr_schools_export.csv
        her cleaned export (36,798 places: school / preschool / ambiguous, with sector and district;
        made by that project's scripts/export_csv.py). Replaces ncr_schools_final.gpkg (39,311), used before 3 Nov 2026.
Output: dashboard/public/local/google_schools.json  [[lat, lon, name, category, "type · sector", reviews], ...]
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(r"C:\projects\ncr-schools\google-maps-scraper\ncr\ncr_schools_export.csv")
OUT = ROOT / "dashboard/public/local"
OUT.mkdir(parents=True, exist_ok=True)

g = pd.read_csv(SRC, low_memory=False)
assert g.latitude.between(26.5, 30.2).all() and g.longitude.between(75.3, 78.6).all(), "points outside the NCR"
print(f"Google Maps school places: {len(g)}  |  {g.type.value_counts().to_dict()}")
clean = lambda v: "" if pd.isna(v) else str(v)
rows = [[round(r.latitude, 5), round(r.longitude, 5), clean(r.name), clean(r.category),
         " · ".join(x for x in (clean(r.type), clean(r.sector)) if x), 0 if pd.isna(r.reviews) else int(r.reviews)]
        for r in g.itertuples()]
(OUT / "google_schools.json").write_text(json.dumps(rows, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
print(f"wrote {OUT / 'google_schools.json'} ({(OUT / 'google_schools.json').stat().st_size / 1e6:.1f} MB)")
