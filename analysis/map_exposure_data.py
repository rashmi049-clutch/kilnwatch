"""
Data for the finished exposure map (step 26).
District totals of children aged 5-14 (WorldPop 2020, M_5+M_10+F_5+F_10) are
joined to the exposure table, giving the share of each district's children living
within 800 m of a firing kiln (cleaned, lower layer). Delhi NCT is excluded from
the analysis and flagged. Also writes the top-district bar chart.
Output: outputs/maps/district_exposure_32643.gpkg, outputs/maps/bar_top_districts.png
"""
from pathlib import Path
import ee, geopandas as gpd, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
ee.Initialize(project="geosync-448701")
dist = gpd.read_file(ROOT / "data/boundaries/ncr_districts_32643.gpkg")
dist["name"] = dist.district.str.replace(" (pre-2023)", "", regex=False)
wp = (ee.ImageCollection("WorldPop/GP/100m/pop_age_sex").filter(ee.Filter.eq("country", "IND")).first()
      .select(["M_5", "M_10", "F_5", "F_10"]).reduce(ee.Reducer.sum()).rename("kids"))
fc = ee.FeatureCollection([ee.Feature(ee.Geometry(g.simplify(0.0005).__geo_interface__), {"name": n})
                           for n, g in zip(dist.name, dist.to_crs(4326).geometry)])
tot = {f["properties"]["name"]: f["properties"]["sum"]
       for f in wp.reduceRegions(fc, ee.Reducer.sum(), 100).getInfo()["features"]}
dist["children_total"] = dist.name.map(tot).round()

ex = pd.read_csv(ROOT / "outputs/tables/exposure_by_district.csv", index_col=0)
ex = ex[ex.layer.str.startswith("lower")]
dist = dist.merge(ex[["kilns", "kilns_with_school_800m", "schools_within_800m", "children_5_14_within_800m"]],
                  left_on="name", right_index=True, how="left").fillna({"kilns": 0, "children_5_14_within_800m": 0})
dist["pct_children_exposed"] = (100 * dist.children_5_14_within_800m / dist.children_total).round(1)
dist["excluded"] = dist.name.str.contains("Delhi").astype(int)
dist.loc[dist.excluded == 1, "pct_children_exposed"] = None
dist.to_file(ROOT / "outputs/maps/district_exposure_32643.gpkg", driver="GPKG")
d = dist[dist.excluded == 0].sort_values("children_5_14_within_800m", ascending=False)
print(d[["name", "kilns", "children_total", "children_5_14_within_800m", "pct_children_exposed"]].to_string(index=False))
print("NCR excl. Delhi: total children", int(d.children_total.sum()), " exposed", int(d.children_5_14_within_800m.sum()),
      f" = {100 * d.children_5_14_within_800m.sum() / d.children_total.sum():.1f}%")

top = d.head(10).iloc[::-1]
fig, ax = plt.subplots(figsize=(4.2, 3.6), dpi=200)
bars = ax.barh(top.name, top.children_5_14_within_800m / 1000, color="#b2182b")
for b, p in zip(bars, top.pct_children_exposed):
    ax.text(b.get_width() + 1, b.get_y() + b.get_height() / 2, f"{p:.0f}%", va="center", fontsize=7, color="#444")
ax.set_xlabel("Children aged 5–14 within 800 m (thousands)", fontsize=7)
ax.set_title("Top 10 districts · label = share of district's children", fontsize=7.5, loc="left")
ax.tick_params(labelsize=7); ax.spines[["top", "right"]].set_visible(False)
ax.set_xlim(0, top.children_5_14_within_800m.max() / 1000 * 1.18)
plt.tight_layout(); plt.savefig(ROOT / "outputs/maps/bar_top_districts.png", transparent=False, facecolor="white")
