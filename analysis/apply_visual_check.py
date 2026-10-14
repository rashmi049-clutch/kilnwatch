"""
Apply the full visual check of near-school kilns, and remove misplaced school points.

1. Kilns. (a) Every firing-verified kiln with a school within 800 m (1,133) was checked
   on Esri World Imagery; points unclear on the current image (haze, cloud, possible
   relict) were re-checked on up to five older Esri Wayback captures
   (analysis/wayback_check.py). 101 are not kilns (parks, stadiums, factories, truck
   and container yards, open town plots, quarries, ponds). They are set to
   kiln_final = False with reason "visual check: not a kiln".
   (b) GEE re-check: kilns away from schools that fired in fewer than 8 dry-season
   months, Nov 2023 - Jun 2026 (monthly_firing.py; threshold from the eye-checked
   kilns, where it flags 64% of non-kilns and 12% of kilns), were all checked by eye
   too: 65 of 218 were not kilns.
   Verdicts: outputs/tables/visual_check_near_schools.csv

2. Schools. Points shared by schools from DIFFERENT villages (rounded to 1 m) are
   default or office coordinates, not school locations (e.g. 40 schools from 13 Meerut
   villages on one spot). They are dropped from use_strict; a primary and an upper
   primary school of the same village on one point (shared campus) are kept.
   The previous flag is kept as use_strict_v1.

Also rewrites the map layers that QGIS styles (kilns_final, schools_map, 800 m zones).
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
DET = ROOT / "data/kilns/detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg"
SCH = ROOT / "data/schools/ncr_schools_32643.gpkg"

det = gpd.read_file(DET)
vc = pd.read_csv(ROOT / "outputs/tables/visual_check_near_schools.csv")
bad = vc.loc[vc.verdict == "not_kiln", "det_index"].to_numpy()
already = det.nonkiln_reason.fillna("").str.startswith("visual check")
assert (det.loc[bad, "kiln_final"] | already.loc[bad]).all(), "visual check covers only kilns in the final layer"
det["visual_check"] = ""
det.loc[vc.det_index, "visual_check"] = vc.set_index("det_index").verdict
det.loc[bad, "kiln_final"] = False
det.loc[bad, "nonkiln_reason"] = "visual check: not a kiln"
weak = vc.loc[(vc.verdict == "not_kiln") & vc.group.str.contains("GEE"), "det_index"]
det.loc[weak, "nonkiln_reason"] = "visual check: not a kiln (GEE weak firing)"
det.to_file(DET, driver="GPKG")
print(f"kilns: removed {len(bad)}; final layer now {int(det.kiln_final.sum())}")

sch = gpd.read_file(SCH)
if "use_strict_v1" not in sch:
    sch["use_strict_v1"] = sch.use_strict
key = sch.geometry.x.round(0).astype(int).astype(str) + "_" + sch.geometry.y.round(0).astype(int).astype(str)
nvil = sch[sch.use_strict_v1].groupby(key[sch.use_strict_v1]).vilname.nunique()
sch["stacked_multivillage"] = key.map(nvil).fillna(1).gt(1) & sch.use_strict_v1
sch["use_strict"] = sch.use_strict_v1 & ~sch.stacked_multivillage
sch.to_file(SCH, driver="GPKG")
print(f"schools: dropped {int(sch.stacked_multivillage.sum())} stacked multi-village points; "
      f"use_strict now {int(sch.use_strict.sum())} (was {int(sch.use_strict_v1.sum())})")

# map layers styled in QGIS
k = det[det.kiln_final]
k[["conf", "geometry"]].to_file(ROOT / "outputs/maps/kilns_final_32643.gpkg", driver="GPKG")
s = sch[sch.use_strict].copy()
s["exposed"] = (cKDTree(np.c_[k.geometry.x, k.geometry.y]).query(np.c_[s.geometry.x, s.geometry.y])[0] <= 800).astype(int)
s[["schcd", "exposed", "geometry"]].to_file(ROOT / "outputs/maps/schools_map_32643.gpkg", driver="GPKG")
zone = gpd.GeoDataFrame(geometry=[k.buffer(800, resolution=16).union_all()], crs=k.crs)
zone.to_file(ROOT / "data/kilns/firing_kilns_800m_zone_v2_32643.gpkg", driver="GPKG")
print("map layers rewritten; exposed schools on map:", int(s.exposed.sum()))
