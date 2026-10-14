"""
Remove non-kiln heat sources from the firing-verified layer (two checks, union).

1 Location: inside an OSM aerodrome, power plant or works, an industrial estate
  >= 10 ha, or a named non-brick facility (ways and relations;
  heat_source_check.py). Small unnamed industrial polygons are kept - they are
  brick fields mapped as industrial land (2% monsoon-hot, like kilns).
2 Seasonality: monsoon hot frequency >= 0.30 (monsoon_heat.py). Cut-off = 99th
  percentile at the 4,114 reference kilns, so at most ~1% of real kilns are lost.

Agreement: 48% of location-flagged points are monsoon-hot vs 4% of the rest.
Writes columns monsoon_hot, nonkiln_reason, kiln_final into the 2023-24
filtered detections file and data/kilns/nonkiln_removed_32643.gpkg.
"""
from pathlib import Path
import geopandas as gpd, numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
K = ROOT / "data" / "kilns"
F = K / "detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg"

m = pd.read_parquet(K / "monsoon_heat.parquet")
cut = float(m[m.group == "reference"].monsoon_hot.quantile(0.99))
det = gpd.read_file(F)
det["monsoon_hot"] = m[m.group == "firing"].set_index("det_index").monsoon_hot.reindex(det.index)

src = gpd.read_file(ROOT / "data/boundaries/osm_heat_sources_32643.gpkg")
poly = src[src.geom_type.isin(["Polygon", "MultiPolygon"])]
j = gpd.sjoin(det[det.fires], poly, predicate="within")
hit = j[j.kind.isin(["aerodrome", "power_plant", "works"]) | (j.ha >= 10)
        | ((j.name != "") & ~j.name.str.contains("rick|iln", case=False, na=False))]
place = hit.groupby(level=0).apply(lambda d: "; ".join(sorted({f"{k}{' ' + n if n else ''}" for k, n in zip(d["kind"], d["name"])})))

det["nonkiln_reason"] = ""
loc = det.index.isin(place.index)
mon = det.fires & (det.monsoon_hot >= cut)
det.loc[loc, "nonkiln_reason"] = "location: " + place.reindex(det.index[loc]).values
det.loc[mon, "nonkiln_reason"] = det.loc[mon, "nonkiln_reason"].where(det.loc[mon, "nonkiln_reason"] == "", det.loc[mon, "nonkiln_reason"] + " + ") \
    + f"monsoon-hot {cut:.2f}+"
det["kiln_final"] = det.fires & (det.nonkiln_reason == "")
det.to_file(F, driver="GPKG")
det[det.fires & ~det.kiln_final].to_file(K / "nonkiln_removed_32643.gpkg", driver="GPKG")

print(f"monsoon cut-off (reference 99th pct): {cut:.3f}")
print("firing-verified:", int(det.fires.sum()))
print("removed by location only:", int((loc & ~mon).sum()), " monsoon only:", int((mon & ~loc).sum()), " both:", int((loc & mon).sum()))
print("kept as kilns:", int(det.kiln_final.sum()))
ref_lost = float((m[m.group == "reference"].monsoon_hot >= cut).mean())
print(f"reference kilns at/above cut-off: {100 * ref_lost:.2f}% -> ~{ref_lost * det.fires.sum():.0f} real kilns expected among removals")
