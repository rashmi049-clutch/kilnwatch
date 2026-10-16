"""
Sensitivity of the headline to the 166 removals made on Claude's Esri judgement
alone (101 near schools, 65 weak firers), which the analyst did not review.

On the analyst-reviewed last pass, 7 of Claude's 47 "not a kiln" calls (15%) were
in fact kilns, so some of the 166 are probably real kilns. Rather than re-judge them
(bulk image checking is ruled out), the headline is reported as a range:
    final layer (all 210 removals applied)                  -> lower end
    final layer + the 166 unreviewed removals restored       -> upper end
Expected value at the measured 15% error: lower + 0.15 x (upper - lower).

Output: outputs/tables/exposure_sensitivity_removals.csv
"""
from pathlib import Path

import ee
import geopandas as gpd
import pandas as pd

import exposure as ex

ROOT = Path(__file__).resolve().parents[1]
ee.Initialize(project="geosync-448701")
det = gpd.read_file(ROOT / "data/kilns/detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
vc = pd.read_csv(ROOT / "outputs/tables/visual_check_near_schools.csv")
reviewed = vc.group.str.contains("Rashmi|analyst", case=False, na=False) | vc.note.fillna("").str.contains("reviewed by Rashmi")
claude_only = vc[(vc.verdict == "not_kiln") & ~reviewed].det_index
print("unreviewed removals:", len(claude_only))
sch = gpd.read_file(ROOT / "data/schools/ncr_schools_32643.gpkg")
sch = sch[sch.use_strict][["schcd", "geometry"]].reset_index(drop=True)
dist = gpd.read_file(ROOT / "data/boundaries/ncr_districts_32643.gpkg")
dist["district"] = dist.district.str.replace(" (pre-2023)", "", regex=False)

rows = []
for label, k in (("final (210 removed)", det[det.kiln_final]),
                 ("unreviewed removals restored", det[det.kiln_final | det.index.isin(claude_only)])):
    t, _ = ex.run(k.reset_index(drop=True), sch, dist, label)
    t = t[~t.index.str.contains("Delhi")]
    rows.append({"layer": label, "kilns": int(t.kilns.sum()), "schools": int(t.schools_within_800m.sum()),
                 "children": int(t.children_5_14_within_800m.sum()),
                 "kilns_near_school_pct": round(100 * t.kilns_with_school_800m.sum() / t.kilns.sum(), 1)})
out = pd.DataFrame(rows)
lo, hi = out.iloc[0], out.iloc[1]
out.loc[len(out)] = {"layer": "expected at 15% error", "kilns": round(lo.kilns + 0.15 * (hi.kilns - lo.kilns)),
                     "schools": round(lo.schools + 0.15 * (hi.schools - lo.schools)),
                     "children": round(lo.children + 0.15 * (hi.children - lo.children)),
                     "kilns_near_school_pct": None}
out.to_csv(ROOT / "outputs/tables/exposure_sensitivity_removals.csv", index=False)
print(out.to_string(index=False))
