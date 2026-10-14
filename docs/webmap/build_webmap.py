"""
Step 25 - build the interactive web map (single self-contained HTML page).

Data are packed compactly into the page (the artifact host blocks external
tiles and fetches, so no basemap; districts, kilns, zones and schools are drawn
from our own vectors with Leaflet on canvas).

    kilns    : cleaned firing-verified layer (kiln_final), with 2023-24 firing
               frequency, 2025-26 status (step 14), schools within 800 m,
               nearest school, district, and the visual-audit verdict if audited
    schools  : location-checked UDISE schools (use_strict), exposed flag, name
    districts: share of children 5-14 within 800 m (map_exposure_data.py)

Output: docs/webmap/index.html  (template: docs/webmap/template.html)
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

det = gpd.read_file(ROOT / "data/kilns/detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
k = det[det.kiln_final].copy()
chg = gpd.read_file(ROOT / "data/kilns/kilns_change_32643.gpkg")
chg = chg[chg.status != "new"]
j = cKDTree(np.c_[chg.geometry.x, chg.geometry.y]).query(np.c_[k.geometry.x, k.geometry.y])
k["status26"] = np.where(j[0] < 1, chg.status.values[j[1]], "")

sch = gpd.read_file(ROOT / "data/schools/ncr_schools_32643.gpkg")
sch = sch[sch.use_strict].reset_index(drop=True)
S = np.c_[sch.geometry.x, sch.geometry.y]
K = np.c_[k.geometry.x, k.geometry.y]
k["n_sch"] = [len(x) for x in cKDTree(S).query_ball_point(K, 800)]
k["near_m"] = cKDTree(S).query(K)[0].round()
sch["kiln_m"] = cKDTree(K).query(S)[0].round()

dist = gpd.read_file(ROOT / "outputs/maps/district_exposure_32643.gpkg")
k = gpd.sjoin(k, dist[["name", "geometry"]], predicate="within", how="left")
audit = pd.read_csv(ROOT / "outputs/tables/kiln_audit_25.csv").set_index("det_index").verdict
k["audit"] = k.index.map(audit).fillna("")

k4 = k.to_crs(4326)
kilns = [[round(g.y, 5), round(g.x, 5), round(100 * h), {"continuing": 1, "stopped": 0}.get(st, -1), int(n), int(m), d or "", a]
         for g, h, st, n, m, d, a in zip(k4.geometry, k4.hot_frac, k4.status26, k4.n_sch, k4.near_m, k4.name, k4.audit)]
# school identity from the UDISE register, as lookup indices to keep the page small
sch["kilns_800m"] = [len(x) for x in cKDTree(K).query_ball_point(S, 800)]
MGMT = {"Department of Education": "Government (Dept. of Education)", "Local body": "Government (local body)",
        "Private Unaided (Recognized)": "Private, recognised", "Unrecognized": "Private, unrecognised",
        "Government Aided": "Government-aided", "Madarsa recognized (by Wakf board/Madarsa Board)": "Madarsa, recognised",
        "Madarsa unrecognized": "Madarsa, unrecognised"}
lut = {k: sorted(set(v)) for k, v in {"cat": sch.school_cat.fillna("").str.strip(),
                                       "mgmt": sch.management.fillna("").str.strip().map(lambda m: MGMT.get(m, m)),
                                       "typ": sch.school_typ.fillna("").str.strip(),
                                       "dist": sch.district.fillna("").str.replace(" (pre-2023)", "", regex=False)}.items()}
code = {k: {v: i for i, v in enumerate(vals)} for k, vals in lut.items()}
s4 = sch.to_crs(4326)
schools = [[round(g.y, 5), round(g.x, 5), int(km <= 800), int(km), str(n).title(), str(v).title(), int(nk),
            code["cat"][str(c or "").strip()], code["mgmt"][MGMT.get(str(mg or "").strip(), str(mg or "").strip())],
            code["typ"][str(t or "").strip()], int(r == "2"), code["dist"][(d or "").replace(" (pre-2023)", "")]]
           for g, km, n, v, nk, c, mg, t, r, d in zip(s4.geometry, s4.kiln_m, s4.schname, s4.vilname, s4.kilns_800m,
                                                     s4.school_cat, s4.management, s4.school_typ, s4.rururb, s4.district)]
d4 = dist.to_crs(4326)
d4["geometry"] = d4.geometry.simplify(0.002)
feats = []
for r in d4.itertuples():
    feats.append({"type": "Feature", "geometry": json.loads(gpd.GeoSeries([r.geometry]).to_json())["features"][0]["geometry"],
                  "properties": {"n": r.name, "pct": None if r.excluded else r.pct_children_exposed,
                                 "kids": int(r.children_5_14_within_800m or 0), "tot": int(r.children_total or 0),
                                 "k": int(r.kilns or 0), "s": int(r.schools_within_800m or 0) if r.schools_within_800m == r.schools_within_800m else 0,
                                 "x": int(r.excluded),
                                 "lp": [round(r.geometry.representative_point().y, 4), round(r.geometry.representative_point().x, 4)]}})
# Sentinel-2 chips (make_chips_qgis.py) were tried and removed: at 10 m a kiln is a blur.
data = {"kilns": kilns, "schools": schools, "lut": lut, "districts": {"type": "FeatureCollection", "features": feats}}
blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False)

css = (HERE / "leaflet-1.9.4.css").read_text(encoding="utf-8")
html = (HERE / "template.html").read_text(encoding="utf-8")
html = html.replace("/*LEAFLET_CSS*/", css).replace("__DATA__", blob.replace("</", "<\\/"))
(HERE / "index.html").write_text(html, encoding="utf-8")
print(f"kilns {len(kilns)}  schools {len(schools)}  exposed {sum(s[2] for s in schools)}  page {len(html)/1e6:.2f} MB")
