"""
Cross-check UDISE school points against OpenStreetMap schools (amenity=school,
nodes/ways/relations, NCR bounding box; data/osm/osm_schools_ncr.json, ODbL).

A register school is matched to an OSM school when (a) the OSM school lies within
1,000 m of the register point and (b) the names agree after normalisation (common
words such as "primary", "school", "govt", "P.S." removed; similarity >= 0.8 or one
name contained in the other). Where matched, the OSM position (building or campus
centre) is taken as the corrected location. Unmatched schools keep the register point.

REJECTED (19 Oct 2026): OSM has ~2,400 schools in the NCR against ~44,000 in the register; only
9 of 4,158 register schools within 1.5 km of a kiln found an OSM match, mostly urban Delhi,
and loose name matching produced false pairs. The register points are kept; the corrected
columns are NOT used. Kept as a tested, rejected method.

Output (when run): data/schools/ncr_schools_32643.gpkg gains osm_match, osm_name, osm_dist_m,
        x_fix/y_fix (corrected UTM coordinates);
        outputs/tables/school_osm_match_summary.csv
"""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
STOP = r"\b(govt|government|g|p|s|u|j|h|sr|sec|senior|secondary|higher|high|primary|upper|middle|junior|" \
       r"school|vidyalaya|vidhyalaya|pathshala|public|composite|ps|ups|jhs|gps|gms|ghs|gsss|gss|bal|kanya|" \
       r"inter|college|model|english|medium|the|of|and|no|sch)\b"


def norm(s):
    s = re.sub(r"[^a-z ]", " ", str(s).lower())
    s = re.sub(STOP, " ", s)
    return " ".join(s.split())


osm = json.load(open(ROOT / "data/osm/osm_schools_ncr.json"))["elements"]
rows = []
for e in osm:
    name = e.get("tags", {}).get("name") or e.get("tags", {}).get("name:en")
    lat = e.get("lat", e.get("center", {}).get("lat")); lon = e.get("lon", e.get("center", {}).get("lon"))
    if name and lat:
        rows.append({"osm_name": name, "n": norm(name), "geometry": Point(lon, lat)})
o = gpd.GeoDataFrame(rows, crs=4326).to_crs(32643)
o = o[o.n.str.len() >= 3].reset_index(drop=True)

sch = gpd.read_file(ROOT / "data/schools/ncr_schools_32643.gpkg")
S = np.c_[sch.geometry.x, sch.geometry.y]
cand = cKDTree(np.c_[o.geometry.x, o.geometry.y]).query_ball_point(S, 1000)
match = np.full(len(sch), -1); dist = np.full(len(sch), np.nan)
for i, cs in enumerate(cand):
    if not cs:
        continue
    n = norm(sch.schname.iat[i])
    if len(n) < 3:
        continue
    best, bscore = -1, 0
    for c in cs:
        on = o.n.iat[c]
        sc = 1.0 if (n in on or on in n) else SequenceMatcher(None, n, on).ratio()
        if sc > bscore:
            best, bscore = c, sc
    if bscore >= 0.8:
        match[i] = best
        dist[i] = float(np.hypot(*(S[i] - [o.geometry.x.iat[best], o.geometry.y.iat[best]])))
m = match >= 0
sch["osm_match"] = m
sch["osm_name"] = np.where(m, o.osm_name.reindex(match).values, "")
sch["osm_dist_m"] = np.round(dist, 0)
sch["x_fix"] = np.where(m, o.geometry.x.reindex(match).values, S[:, 0])
sch["y_fix"] = np.where(m, o.geometry.y.reindex(match).values, S[:, 1])
sch.to_file(ROOT / "data/schools/ncr_schools_32643.gpkg", driver="GPKG")

det = gpd.read_file(ROOT / "data/kilns/detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
k = det[det.kiln_final]
K = cKDTree(np.c_[k.geometry.x, k.geometry.y])
u = sch.use_strict
near = K.query(S)[0] <= 1500
summ = pd.DataFrame([{
    "osm_schools_named": len(o), "register_schools_used": int(u.sum()),
    "matched_all": int((m & u).sum()), "matched_within_1500m_of_kiln": int((m & u & near).sum()),
    "used_within_1500m_of_kiln": int((u & near).sum()),
    "median_shift_m": float(np.nanmedian(dist[m & u])) if (m & u).any() else None}])
summ.to_csv(ROOT / "outputs/tables/school_osm_match_summary.csv", index=False)
print(summ.T.to_string())
print(sch.loc[m & u, ["schname", "osm_name", "osm_dist_m"]].sample(min(12, int((m & u).sum())), random_state=1).to_string())
