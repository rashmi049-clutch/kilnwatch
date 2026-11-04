"""
School lists with source and status for every register school in NCR excluding Delhi.
Run after apply_visual_check (which sets use_strict and the removal flags).

Output: outputs/tables/ncr_school_list.csv              every register school, status = used or removal reason
        outputs/tables/schools_within_800m_of_kiln.csv  used schools with >= 1 final kiln within 800 m
Both carry the analyst's school-check verdict (outputs/tables/school_check_verdicts_138.csv)
where the school was among the 138 audited points: confirmed_label / unverified / wrong_point.
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "UDISE / NIC SchoolGIS via datameet/udise_schools"

sch = gpd.read_file(ROOT / "data/schools/ncr_schools_32643.gpkg")
sch = sch[sch.state != "Delhi"].copy()
sch["schcd"] = sch.schcd.astype(str)
k = gpd.read_file(ROOT / "outputs/maps/kilns_final_32643.gpkg")
kxy = np.c_[k.geometry.x, k.geometry.y]
sxy = np.c_[sch.geometry.x, sch.geometry.y]
sch["nearest_kiln_m"] = cKDTree(kxy).query(sxy)[0].round(0)
sch["kilns_800m"] = [len(i) for i in cKDTree(kxy).query_ball_point(sxy, 800)]

# first reason that applies, in the order the filters were built
sch["status"] = np.select(
    [~sch.use_strict_v1, sch.far_from_buildings, sch.stacked_multivillage, sch.reported_wrong,
     sch.duplicate_of.ne("")],
    ["removed: failed location check (wrong district or >300 m from built-up)",
     "removed: >50 m from buildings",
     "removed: point shared with other villages",
     "removed: reported wrong by analyst",
     "removed: duplicate of another UDISE code"],
    default="used")
assert (sch.status == "used").eq(sch.use_strict).all()

v = pd.read_csv(ROOT / "outputs/tables/school_check_verdicts_138.csv", dtype={"schcd": str})
sch["analyst_verdict"] = sch.schcd.map(v.set_index("schcd").verdict).fillna("")
sch["source"] = SOURCE

cols = ["schcd", "schname", "school_cat", "management", "vilname", "district", "state", "lat", "lon",
        "nearest_kiln_m", "kilns_800m", "status", "analyst_verdict", "source"]
out = sch[cols].sort_values(["district", "schname"])
out.to_csv(ROOT / "outputs/tables/ncr_school_list.csv", index=False, encoding="utf-8-sig")
near = out[(out.status == "used") & (out.kilns_800m > 0)].sort_values("nearest_kiln_m")
near.to_csv(ROOT / "outputs/tables/schools_within_800m_of_kiln.csv", index=False, encoding="utf-8-sig")
print(out.status.value_counts().to_string())
print(f"schools within 800 m of a kiln: {len(near)}  |  analyst verdicts among them: "
      f"{near.analyst_verdict.replace('', np.nan).value_counts().to_dict()}")
