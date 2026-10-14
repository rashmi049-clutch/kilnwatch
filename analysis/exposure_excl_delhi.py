"""
Headline exposure numbers for the NCR excluding Delhi NCT (kilns are not permitted in
Delhi; the few detections there are edge cases). Summed from the per-district table,
whose 800 m zones are clipped to each district, so districts add up without double counting.

Output: outputs/tables/exposure_summary_excl_delhi.csv
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
t = pd.read_csv(ROOT / "outputs/tables/exposure_by_district.csv", index_col=0)
t = t[~t.index.str.contains("Delhi")]
UP = ["Baghpat", "Bulandshahr", "Gautam Buddha Nagar", "Ghaziabad", "Hapur", "Meerut", "Muzaffarnagar", "Shamli"]
rows = []
for layer, g in t.groupby("layer"):
    kids = g.children_5_14_within_800m
    st = lambda names: round(100 * kids[g.index.isin(names)].sum() / kids.sum(), 1)
    raj = [i for i in g.index if "Alwar" in i or "Bharatpur" in i]
    rows.append({"layer": layer, "kilns": int(g.kilns.sum()),
                 "H1_pct": round(100 * g.kilns_with_school_800m.sum() / g.kilns.sum(), 1),
                 "schools": int(g.schools_within_800m.sum()), "children": int(kids.sum()),
                 "top3_pct": round(100 * kids.nlargest(3).sum() / kids.sum(), 1),
                 "UP_pct": st(UP), "Rajasthan_pct": st(raj),
                 "Haryana_pct": round(100 - st(UP) - st(raj), 1)})
out = pd.DataFrame(rows)
out.to_csv(ROOT / "outputs/tables/exposure_summary_excl_delhi.csv", index=False)
print(out.to_string(index=False))
