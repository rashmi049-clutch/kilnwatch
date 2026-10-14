"""
Second Google Earth audit: 30 random kilns from the part of the final layer that no
one has yet looked at - kilns with NO school within 800 m that fire strongly (>= 8
fired dry-season months, Nov 2023 - Jun 2026, so not in the GEE weak-firing check).
Every other kiln was checked by eye on Esri imagery. Checked by the analyst on dated
Google Earth imagery (different imagery, different rater), it gives an independent
precision estimate for the unchecked remainder.
Verdicts: active / relict / not_kiln / unclear (same rule as audit 1).
Output: outputs/kml/kiln_audit2_30.kml, outputs/tables/kiln_audit2_30.csv
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
det = gpd.read_file(ROOT / "data/kilns/detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
k = det[det.kiln_final].copy()
sch = gpd.read_file(ROOT / "data/schools/ncr_schools_32643.gpkg")
sch = sch[sch.use_strict_v1]                       # widest school set: anything near any school was checked
k["near"] = cKDTree(np.c_[sch.geometry.x, sch.geometry.y]).query(np.c_[k.geometry.x, k.geometry.y])[0] <= 800

m = pd.read_parquet(ROOT / "data/kilns/monthly_firing.parquet")
mo = pd.PeriodIndex(m.month, freq="M").month
m = m[((mo >= 11) | (mo <= 6)) & (m.n >= 2)]
fired = (m.hot >= 0.3).groupby(m.det_index).sum()
k["fired_months"] = k.index.map(fired).fillna(0)

old = set(pd.read_csv(ROOT / "outputs/tables/kiln_audit_25.csv").det_index)
pool = k[~k.near & (k.fired_months >= 8) & ~k.index.isin(old)]
s = pool.sample(30, random_state=2027).to_crs(4326)
s["audit_no"] = range(1, 31)
s["det_index"] = s.index
s["lat"], s["lon"] = s.geometry.y.round(5), s.geometry.x.round(5)

pm = [f"""<Placemark><name>{r.audit_no}</name>
<description>Detection {r.det_index}. Use the history slider (2022-2025): active / relict / not a kiln / unclear.</description>
<LookAt><longitude>{r.lon}</longitude><latitude>{r.lat}</latitude><range>700</range><tilt>0</tilt><heading>0</heading></LookAt>
<Point><coordinates>{r.lon},{r.lat},0</coordinates></Point></Placemark>""" for r in s.itertuples()]
kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>KilnWatch audit 2 - 30 random unchecked kilns</name>
{''.join(pm)}
</Document></kml>"""
(ROOT / "outputs/kml/kiln_audit2_30.kml").write_text(kml, encoding="utf-8")
s[["audit_no", "det_index", "lat", "lon", "hot_frac", "fired_months"]].assign(verdict="", note="").to_csv(
    ROOT / "outputs/tables/kiln_audit2_30.csv", index=False)
print(f"pool {len(pool)} unchecked kilns; sample 30")
