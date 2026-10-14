"""
Step 24 - How much smoke do the kilns put out, and how much of it is next to schools?

Simple activity x emission-factor estimate for one firing season (2023-24):

    PM2.5 (t) = bricks fired x brick mass (kg) x EF (g PM2.5 / kg fired brick) / 1e6

Emission factors - World Bank (2020) "Dirty Stacks, High Stakes", Table 2.1
(averages collated from Weyant et al. 2014, Greentech 2012 and others):
    zigzag (ZZK)          PM2.5 0.12   BC 0.035 g/kg fired brick
    fixed chimney (FCK)   PM2.5 0.21   BC 0.17  g/kg fired brick
NCR kilns were ordered to convert to zigzag in 2017-18, but the same report
says the ZZK factors "seem too optimistic" because most conversions are not
built to standard. So zigzag = low case, fixed-chimney = high case.

Activity (bricks per kiln per season) - ASSUMED, not measured:
    low 4 million  (CSE retrofit model kiln, 40 lakh/yr)
    high 6 million (~250 billion bricks/yr in India / ~44,000 kilns = 5.7 million)
Brick mass 3 kg (World Bank Table 2.1 footnote).

Per-kiln split: we cannot see bricks from space, but we can see how often a
kiln fires. Each kiln's share of the season total is proportional to its
2023-24 firing frequency (hot_frac), so busier kilns get more; the NCR total is
unchanged by this choice.

Output:
    outputs/tables/emissions_summary.csv
    outputs/tables/emissions_by_district.csv
    outputs/tables/emissions_top_schools.csv
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
R, MASS = 800, 3.0
CASES = {  # name: (bricks per kiln per season, PM2.5 g/kg, BC g/kg)
    "low (zigzag, 4 M bricks)": (4e6, 0.12, 0.035),
    "high (fixed chimney, 6 M bricks)": (6e6, 0.21, 0.17),
}

det = gpd.read_file(ROOT / "data/kilns/detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
k = det[det.kiln_final].copy()
dist = gpd.read_file(ROOT / "outputs/maps/district_exposure_32643.gpkg")
k = gpd.sjoin(k, dist[["name", "excluded", "geometry"]], predicate="within", how="left").drop(columns="index_right")
k = k[k.excluded != 1].copy()            # Delhi excluded, as in the exposure analysis

sch = gpd.read_file(ROOT / "data/schools/ncr_schools_32643.gpkg")
sch = sch[sch.use_strict].reset_index(drop=True)
K, S = np.c_[k.geometry.x, k.geometry.y], np.c_[sch.geometry.x, sch.geometry.y]
k["near_school"] = [len(x) > 0 for x in cKDTree(S).query_ball_point(K, R)]
w = (k.hot_frac / k.hot_frac.sum()).to_numpy()   # share of NCR production

rows = []
for case, (bricks, ef_pm, ef_bc) in CASES.items():
    tot_kg = bricks * len(k) * MASS
    pm, bc = tot_kg * ef_pm / 1e6, tot_kg * ef_bc / 1e6       # tonnes
    k[f"pm_{case[:4].strip()}"] = w * pm
    near = w[k.near_school.to_numpy()].sum()
    rows.append({"case": case, "kilns": len(k), "bricks_bn": bricks * len(k) / 1e9,
                 "pm25_t": pm, "bc_t": bc, "pm25_near_school_t": pm * near,
                 "share_near_school": near, "share_kilns_near_school": k.near_school.mean()})
summ = pd.DataFrame(rows)
summ.to_csv(ROOT / "outputs/tables/emissions_summary.csv", index=False)

bd = (k.groupby("name").agg(kilns=("hot_frac", "size"), near=("near_school", "sum"),
                             pm_low=("pm_low", "sum"), pm_high=("pm_high", "sum"))
      .sort_values("pm_low", ascending=False))
bd["pm_near_low"] = k[k.near_school].groupby("name").pm_low.sum()
bd = bd.fillna(0)
bd.to_csv(ROOT / "outputs/tables/emissions_by_district.csv")

# schools with the most kiln smoke emitted within 800 m (low case)
pm_low = k.pm_low.to_numpy()
idx = cKDTree(K).query_ball_point(S, R)
sch["kilns_800m"] = [len(i) for i in idx]
sch["pm_low_800m"] = [pm_low[i].sum() for i in idx]
top = (sch[sch.kilns_800m > 0].sort_values("pm_low_800m", ascending=False)
       [["schname", "vilname", "district", "kilns_800m", "pm_low_800m"]].head(15)
       if "district" in sch else sch.sort_values("pm_low_800m", ascending=False).head(15))
top.to_csv(ROOT / "outputs/tables/emissions_top_schools.csv", index=False)

# ---- layers for the finished emissions map (step 26)
M = ROOT / "outputs/maps"
k[["pm_low", "pm_high", "hot_frac", "near_school", "name", "geometry"]].to_file(M / "kilns_emissions_32643.gpkg", driver="GPKG")
t15 = sch[sch.kilns_800m > 0].sort_values("pm_low_800m", ascending=False).head(15).copy()
t15["rank"] = range(1, 16)
t15[["rank", "schname", "vilname", "district", "kilns_800m", "pm_low_800m", "geometry"]].to_file(M / "schools_top15_32643.gpkg", driver="GPKG")
de = dist.merge(bd[["pm_low", "pm_high", "pm_near_low"]], left_on="name", right_index=True, how="left")
de["share_near"] = (100 * de.pm_near_low / de.pm_low).round(0)
de.loc[de.excluded == 1, ["pm_low", "pm_high", "pm_near_low", "share_near"]] = None
de[["name", "excluded", "kilns", "pm_low", "pm_high", "pm_near_low", "share_near", "geometry"]].to_file(M / "district_emissions_32643.gpkg", driver="GPKG")

import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
tb = de.dropna(subset=["pm_near_low"]).sort_values("pm_near_low", ascending=False).head(10).iloc[::-1]
fig, ax = plt.subplots(figsize=(4.2, 2.9), dpi=200)
bars = ax.barh(tb.name, tb.pm_near_low, color="#7f2704")
for b, p in zip(bars, tb.share_near):
    ax.text(b.get_width() + 4, b.get_y() + b.get_height() / 2, f"{p:.0f}%", va="center", fontsize=7, color="#444")
ax.set_xlabel("PM$_{2.5}$ from kilns within 800 m of a school (t per season, low case)", fontsize=7)
ax.set_title("Top 10 districts · label = share of district's kiln PM$_{2.5}$", fontsize=7.5, loc="left")
ax.tick_params(labelsize=7); ax.spines[["top", "right"]].set_visible(False)
ax.set_xlim(0, tb.pm_near_low.max() * 1.18)
plt.tight_layout(); plt.savefig(M / "bar_emissions_districts.png", facecolor="white")

pd.set_option("display.width", 200)
print(summ.round(3).to_string(index=False))
print(bd.head(10).round(0).to_string())
print(top.round(1).to_string(index=False))
print("schools with >=1 kiln within 800 m:", (sch.kilns_800m > 0).sum(),
      " median kilns:", sch.loc[sch.kilns_800m > 0, "kilns_800m"].median())
