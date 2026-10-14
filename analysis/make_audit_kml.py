"""
Precision audit: 25 random kilns from the final layer (kiln_final), for visual
checking against dated Google Earth imagery. Prompted by a relict kiln found
near Faridabad (detection 3264, excluded here because it is already audited).
Verdicts: active / relict / not_kiln / unclear.
Output: outputs/kml/kiln_audit_25.kml, outputs/tables/kiln_audit_25.csv
"""
from pathlib import Path
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
det = gpd.read_file(ROOT / "data/kilns/detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
k = det[det.kiln_final].drop(index=3264, errors="ignore")
s = k.sample(25, random_state=2026).to_crs(4326)
s["audit_no"] = range(1, 26)
s["det_index"] = s.index
s["lat"], s["lon"] = s.geometry.y.round(5), s.geometry.x.round(5)

pm = []
for r in s.itertuples():
    pm.append(f"""<Placemark><name>{r.audit_no}</name>
<description>Detection {r.det_index}. Check dated imagery Nov 2023 - 2025: active / relict / not a kiln.</description>
<LookAt><longitude>{r.lon}</longitude><latitude>{r.lat}</latitude><range>700</range><tilt>0</tilt><heading>0</heading></LookAt>
<Point><coordinates>{r.lon},{r.lat},0</coordinates></Point></Placemark>""")
kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>KilnWatch audit - 25 random kilns</name>
{''.join(pm)}
</Document></kml>"""
(ROOT / "outputs/kml/kiln_audit_25.kml").write_text(kml, encoding="utf-8")
s[["audit_no", "det_index", "lat", "lon", "conf", "hot_frac"]].assign(verdict="", note="").to_csv(
    ROOT / "outputs/tables/kiln_audit_25.csv", index=False)
print(s[["audit_no", "det_index", "lat", "lon"]].to_string(index=False))
