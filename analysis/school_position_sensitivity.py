"""
How sensitive is the count of schools within 800 m of a kiln to errors in the
school coordinates (UDISE register points, often beside rather than on the school)?

Each school point is moved in a random direction by a random distance and the count
is redone, 500 times per scenario. Distances follow a Rayleigh distribution (the
radial error of a 2-D normal), scaled so that the median offset is 50, 100, 200 or
300 m. The measured evidence: in a check of 30 random schools about half sat on the
building and half on open land beside it, and 81% are within 50 m of WorldCover
built-up land (report, School location accuracy), so 100-200 m is the realistic
range; 300 m is a deliberately pessimistic case.

Kilns are held fixed (final layer, NCR excluding Delhi).
Output: outputs/tables/school_position_sensitivity.csv
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
R, N, SEED = 800.0, 500, 2026

det = gpd.read_file(ROOT / "data/kilns/detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
sch = gpd.read_file(ROOT / "data/schools/ncr_schools_32643.gpkg")
dist = gpd.read_file(ROOT / "data/boundaries/ncr_districts_32643.gpkg")
delhi = dist[dist.district.str.contains("Delhi")].union_all()
k = det[det.kiln_final & ~det.within(delhi)]
s = sch[sch.use_strict & ~sch.within(delhi)]
K = cKDTree(np.c_[k.geometry.x, k.geometry.y])
S = np.c_[s.geometry.x, s.geometry.y]

base = int((K.query(S)[0] <= R).sum())
rng = np.random.default_rng(SEED)
rows = [{"median_offset_m": 0, "mean": base, "p2_5": base, "p97_5": base, "min": base, "max": base}]
for med in (50, 100, 200, 300):
    sigma = med / np.sqrt(2 * np.log(2))           # Rayleigh median = sigma*sqrt(2 ln 2)
    counts = []
    for _ in range(N):
        r = rng.rayleigh(sigma, len(S)); a = rng.uniform(0, 2 * np.pi, len(S))
        counts.append(int((K.query(S + np.c_[r * np.cos(a), r * np.sin(a)])[0] <= R).sum()))
    c = np.array(counts)
    rows.append({"median_offset_m": med, "mean": round(c.mean()), "p2_5": int(np.percentile(c, 2.5)),
                 "p97_5": int(np.percentile(c, 97.5)), "min": int(c.min()), "max": int(c.max())})
out = pd.DataFrame(rows)
out.to_csv(ROOT / "outputs/tables/school_position_sensitivity.csv", index=False)
print(out.to_string(index=False))
# how many schools sit near the 800 m line, where small errors can flip them
d = K.query(S)[0]
print("schools 600-1000 m from a kiln:", int(((d > 600) & (d <= 1000)).sum()), " within 800 m:", base)
