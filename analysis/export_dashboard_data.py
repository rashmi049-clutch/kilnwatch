"""
Export the pipeline outputs as small JSON files for the Next.js dashboard
(dashboard/public/data/). Same selections as docs/webmap/build_webmap.py, so the
dashboard and the web map always show identical numbers.

    kilns.json      [id, lat, lon, firing %, status 2025-26, schools 800 m, nearest school m, district, check]
    schools.json    every location-checked school (use_strict) with kilns within 800 m
    districts.json  GeoJSON, share of children 5-14 within 800 m
    summary.json    headline numbers, the range, H3 stop rates, emissions, provenance
    wayback.json    Esri World Imagery Wayback release per year (for the year slider)

Run after the pipeline (docs/webmap/build_webmap.py step): python analysis/export_dashboard_data.py
"""
import json
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard/public/data"
OUT.mkdir(parents=True, exist_ok=True)

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
sch["kilns_800m"] = [len(x) for x in cKDTree(K).query_ball_point(S, 800)]

dist = gpd.read_file(ROOT / "outputs/maps/district_exposure_32643.gpkg")
k = gpd.sjoin(k, dist[["name", "geometry"]], predicate="within", how="left")
k = k[~k.index.duplicated()]

k4 = k.to_crs(4326)
kilns = [[int(i), round(g.y, 5), round(g.x, 5), round(100 * h), {"continuing": 1, "stopped": 0}.get(st, -1),
          int(n), int(m), d if isinstance(d, str) else "", str(vc or "")]
         for i, g, h, st, n, m, d, vc in zip(k4.index, k4.geometry, k4.hot_frac, k4.status26, k4.n_sch, k4.near_m,
                                              k4.name, k4.visual_check)]

MGMT = {"Department of Education": "Government (Dept. of Education)", "Local body": "Government (local body)",
        "Private Unaided (Recognized)": "Private, recognised", "Unrecognized": "Private, unrecognised",
        "Government Aided": "Government-aided", "Madarsa recognized (by Wakf board/Madarsa Board)": "Madarsa, recognised",
        "Madarsa unrecognized": "Madarsa, unrecognised"}
s4 = sch.to_crs(4326)
clean = lambda v: "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v).strip()
schools = [{"id": clean(c), "lat": round(g.y, 5), "lon": round(g.x, 5), "name": clean(n).title(), "village": clean(v).title(),
            "district": clean(d).replace(" (pre-2023)", ""), "state": clean(st), "cat": clean(cat),
            "mgmt": MGMT.get(clean(mg), clean(mg)), "rural": clean(r) == "2", "kiln_m": int(km), "kilns_800m": int(nk)}
           for c, g, n, v, d, st, cat, mg, r, km, nk in zip(s4.schcd, s4.geometry, s4.schname, s4.vilname, s4.district,
                                                            s4.state, s4.school_cat, s4.management, s4.rururb,
                                                            s4.kiln_m, s4.kilns_800m)]

d4 = dist.to_crs(4326)
d4["geometry"] = d4.geometry.simplify(0.002)
num = lambda v: None if v is None or v != v else v
feats = [{"type": "Feature", "geometry": json.loads(gpd.GeoSeries([r.geometry]).to_json())["features"][0]["geometry"],
          "properties": {"name": r.name, "state": r.state, "excluded": bool(r.excluded),
                         "pct": None if r.excluded else num(r.pct_children_exposed),
                         "children_exposed": int(num(r.children_5_14_within_800m) or 0),
                         "children_total": int(num(r.children_total) or 0), "kilns": int(num(r.kilns) or 0),
                         "kilns_with_school": int(num(r.kilns_with_school_800m) or 0),
                         "schools": int(num(r.schools_within_800m) or 0), "area_km2": round(float(r.area_km2), 1)}}
         for r in d4.itertuples()]

ex = pd.read_csv(ROOT / "outputs/tables/exposure_summary_excl_delhi.csv")
lo, hi = ex.iloc[0], ex.iloc[1]
rng = pd.read_csv(ROOT / "outputs/tables/exposure_sensitivity_removals.csv")
h3 = pd.read_csv(ROOT / "outputs/tables/h3_stop_rates.csv")
em = pd.read_csv(ROOT / "outputs/tables/emissions_summary.csv")
summary = {
    "built": date.today().isoformat(),
    "study_area": "Delhi-NCR excluding Delhi (no kilns in Delhi); UP, Haryana and Rajasthan NCR districts",
    "kilns": int(lo.kilns), "schools_800m": int(lo.schools), "children_800m": int(lo.children),
    "pct_kilns_with_school": float(lo.H1_pct), "upper_all_filtered": {"kilns": int(hi.kilns), "schools": int(hi.schools),
                                                                        "children": int(hi.children)},
    "children_range": json.loads(rng.to_json(orient="records")),   # to_json writes NaN as null
    "stop_rates": h3[["near_school", "kilns", "stopped", "stop_rate_pct"]].to_dict(orient="records"),
    "stop_test": {"diff_pp": float(h3.diff_pp[0]), "ci": [float(h3.ci_low[0]), float(h3.ci_high[0])], "p": float(h3.chi2_p[0])},
    "emissions": [{"case": r.case, "pm25_t": round(r.pm25_t), "bc_t": round(r.bc_t)} for r in em.itertuples()],
    "audit": {"random_kilns": 30, "active": 29, "unclear": 1, "by": "Rashmi Sinha"},
    "sources": [
        {"layer": "Kilns", "source": "Sentinel-2 L2A (ESA Copernicus), YOLO11-OBB detector + SWIR firing test, every kiln checked by eye", "licence": "Copernicus open"},
        {"layer": "Schools", "source": "UDISE+ register (Ministry of Education / NIC SchoolGIS), via DataMeet", "licence": "ODbL (DataMeet)"},
        {"layer": "Children 5-14", "source": "WorldPop 2020 age/sex structures, 100 m", "licence": "CC BY 4.0"},
        {"layer": "Imagery", "source": "Esri World Imagery and Wayback", "licence": "Esri terms, attribution required"},
    ],
}

cfg = requests.get("https://s3-us-west-2.amazonaws.com/config.maptiles.arcgis.com/waybackconfig.json", timeout=60).json()
byyear = {}
for v in cfg.values():
    dd = v["itemTitle"].split("Wayback ")[-1].rstrip(")")
    if dd[:4].isdigit() and int(dd[:4]) >= 2017 and dd > byyear.get(dd[:4], ("", ""))[0]:
        byyear[dd[:4]] = (dd, v["itemURL"].replace("{level}", "{z}").replace("{row}", "{y}").replace("{col}", "{x}"))
wayback = [{"year": y, "date": d, "url": u} for y, (d, u) in sorted(byyear.items())]

dump = lambda name, obj: (OUT / name).write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False, allow_nan=False),
                                                 encoding="utf-8")
# schools near kilns (map layer) as full records; all schools compact (loaded only for search)
near_s = [s for s in schools if s["kiln_m"] <= 800]
cols = ["id", "lat", "lon", "name", "village", "district", "state", "cat", "mgmt", "rural", "kiln_m", "kilns_800m"]
lut = {c: sorted({s[c] for s in schools}) for c in ["district", "state", "cat", "mgmt"]}
ix = {c: {v: i for i, v in enumerate(vals)} for c, vals in lut.items()}
compact = {"cols": cols, "lut": lut,
           "rows": [[ix[c][s[c]] if c in ix else (int(s[c]) if c == "rural" else s[c]) for c in cols] for s in schools]}
(OUT / "schools.json").unlink(missing_ok=True)
dump("kilns.json", kilns); dump("schools_near.json", near_s); dump("schools_all.json", compact)
dump("summary.json", summary); dump("wayback.json", wayback)
dump("districts.json", {"type": "FeatureCollection", "features": feats})
near = sum(s["kiln_m"] <= 800 for s in schools)
print(f"kilns {len(kilns)}  schools {len(schools)} (within 800 m: {near})  districts {len(feats)}  wayback {len(wayback)}")
for f in sorted(OUT.glob("*.json")):
    print(f"  {f.name:16s} {f.stat().st_size/1e6:.2f} MB")
