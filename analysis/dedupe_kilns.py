"""
Remove duplicate detections of the same kiln from the final layer.

Found by the analyst on the web map: two dots on one kiln. Close pairs (< 120 m)
were checked against the hand-labelled reference: pairs matching ONE reference
kiln (duplicates) were 50-68 m apart (17 of 21 below 70 m), pairs matching TWO
reference kilns (real neighbours) were 72-118 m apart (3 of 38 below 70 m).
Cut-off 70 m. Within each group closer than 70 m, the point with the highest
2023-24 hot frequency is kept.
Updates kiln_final / nonkiln_reason in the 2023-24 filtered detections file.
"""
from pathlib import Path
import geopandas as gpd, numpy as np
from scipy.sparse.csgraph import connected_components
from scipy.sparse import coo_matrix
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "data/kilns/detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg"
CUT = 70
det = gpd.read_file(F)
k = det[det.kiln_final]
X = np.c_[k.geometry.x, k.geometry.y]
pairs = np.array(sorted(cKDTree(X).query_pairs(CUT)))
n = len(k)
g = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
_, lab = connected_components(g, directed=False)
k = k.assign(group=lab)
keep = k.sort_values("hot_frac", ascending=False).groupby("group").head(1).index
drop = k.index.difference(keep)
det.loc[drop, "kiln_final"] = False
det.loc[drop, "nonkiln_reason"] = f"duplicate detection (< {CUT} m from a kept kiln)"
det.to_file(F, driver="GPKG")
print("pairs <", CUT, "m:", len(pairs), " duplicates removed:", len(drop), " kilns now:", int(det.kiln_final.sum()))
