"""
Step 17 - H3: do kilns near schools stop firing more often than kilns elsewhere?
Kilns: 2023-24 firing-verified, status from kiln_change.py, Delhi NCT excluded.
Near school: a use_strict school within 800 m. Test: chi-square 2x2 and a
difference in proportions with 95% CI. The firing test's miss rate applies equally
to both groups, so it biases both stop rates the same way, not their difference.
Output: outputs/tables/h3_stop_rates.csv
"""
from pathlib import Path
import geopandas as gpd, numpy as np, pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import chi2_contingency

ROOT = Path(__file__).resolve().parents[1]
k = gpd.read_file(ROOT / "data/kilns/kilns_change_32643.gpkg")
k = k[k.status != "new"].reset_index(drop=True)
# drop non-kiln heat sources (nonkiln_flag.py)
rm = gpd.read_file(ROOT / "data/kilns/nonkiln_removed_32643.gpkg")
k = k[gpd.sjoin_nearest(k, rm[["geometry"]], how="left", max_distance=1).index_right.isna().groupby(level=0).all()].reset_index(drop=True)
d = gpd.read_file(ROOT / "data/boundaries/ncr_districts_32643.gpkg")
k = gpd.sjoin(k, d[["district", "geometry"]], predicate="within")
k = k[~k.district.str.contains("Delhi")].reset_index(drop=True)
s = gpd.read_file(ROOT / "data/schools/ncr_schools_32643.gpkg")
s = s[s.use_strict]
near = cKDTree(np.c_[s.geometry.x, s.geometry.y]).query(np.c_[k.geometry.x, k.geometry.y])[0] <= 800
k["near_school"] = near
k["stopped"] = k.status == "stopped"

t = pd.crosstab(k.near_school, k.stopped)
chi2, p, _, _ = chi2_contingency(t)
g = k.groupby("near_school").stopped.agg(["size", "sum", "mean"])
p1, n1, p0, n0 = g.loc[True, "mean"], g.loc[True, "size"], g.loc[False, "mean"], g.loc[False, "size"]
diff = p1 - p0
se = np.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)
out = pd.DataFrame({"kilns": g["size"], "stopped": g["sum"], "stop_rate_pct": (100 * g["mean"]).round(1)})
out.index = out.index.map({True: "school within 800 m", False: "no school within 800 m"})
print(out.to_string())
print(f"\ndifference (near - far): {100*diff:+.1f} pp, 95% CI {100*(diff-1.96*se):+.1f} to {100*(diff+1.96*se):+.1f}; chi2 p = {p:.3f}")
# also by state, to check the result is not one state's pattern
k["state"] = np.select([k.district.str.contains("Alwar|Bharatpur"), k.district.isin(
    ["Baghpat","Bulandshahr","Gautam Buddha Nagar","Ghaziabad","Hapur","Meerut","Muzaffarnagar","Shamli"])], ["Rajasthan","Uttar Pradesh"], "Haryana")
print((100 * k.groupby(["state", "near_school"]).stopped.mean()).round(1).unstack().to_string())
out.assign(diff_pp=round(100*diff,1), ci_low=round(100*(diff-1.96*se),1), ci_high=round(100*(diff+1.96*se),1), chi2_p=round(p,4)).to_csv(ROOT / "outputs/tables/h3_stop_rates.csv")
