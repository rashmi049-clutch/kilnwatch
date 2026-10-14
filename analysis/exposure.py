"""
Step 15 - Schools and children within 800 m of a brick kiln (CPCB siting distance).

Kiln layers (2023-24):
    lower   firing-verified kilns (3,447; est. precision 0.96)  -> headline, "at least"
    upper   all land-cover-filtered detections (6,140; precision ~0.71)
Schools: use_strict (district label matches location AND <= 300 m from built-up).
Children: WorldPop 2020, ages 5-14 (M_5, M_10, F_5, F_10), summed inside the
union of 800 m buffers per district, so overlapping zones count people once.

Hypotheses (recorded 27 Sep 2026):
    H1  >= 25% of kilns have a school within 800 m       (rejected if < 10%)
    H2  top 3 districts hold > 50% of exposed children   (rejected if spread evenly)

Output:
    outputs/tables/exposure_by_district.csv
    outputs/tables/exposure_summary.csv
"""

from pathlib import Path

import ee
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
UTM, R = "EPSG:32643", 800


def children(zones: gpd.GeoDataFrame) -> pd.Series:
    """WorldPop 5-14 population inside each zone polygon (dissolved per district)."""
    wp = (ee.ImageCollection("WorldPop/GP/100m/pop_age_sex").filter(ee.Filter.eq("country", "IND")).first()
          .select(["M_5", "M_10", "F_5", "F_10"]).reduce(ee.Reducer.sum()).rename("kids"))
    out = {}
    for r in zones.to_crs(4326).itertuples():
        geom = ee.Geometry(r.geometry.simplify(0.0003).__geo_interface__)
        v = wp.reduceRegion(ee.Reducer.sum(), geom, scale=100, maxPixels=1e10).get("kids").getInfo()
        out[r.district] = v or 0.0
    return pd.Series(out)


def run(kilns: gpd.GeoDataFrame, schools: gpd.GeoDataFrame, districts: gpd.GeoDataFrame, label: str):
    K = np.c_[kilns.geometry.x, kilns.geometry.y]
    S = np.c_[schools.geometry.x, schools.geometry.y]
    ktree, stree = cKDTree(K), cKDTree(S)
    kiln_has_school = np.array([len(x) > 0 for x in stree.query_ball_point(K, R)])
    school_exposed = ktree.query(S)[0] <= R

    kd = gpd.sjoin(kilns.assign(has_school=kiln_has_school), districts[["district", "geometry"]], predicate="within")
    sd = gpd.sjoin(schools.assign(exposed=school_exposed), districts[["district", "geometry"]].rename(columns={"district": "district_poly"}), predicate="within")

    zones = (gpd.GeoDataFrame(kd[["district"]], geometry=kd.buffer(R, resolution=12), crs=UTM)
             .dissolve("district").reset_index())
    # clip each district's zone to the district so a buffer spilling over a line is counted where it lies
    zones = gpd.overlay(gpd.GeoDataFrame(geometry=[zones.union_all()], crs=UTM), districts[["district", "geometry"]], how="intersection")
    kids = children(zones)

    tab = pd.DataFrame({
        "kilns": kd.groupby("district").size(),
        "kilns_with_school_800m": kd.groupby("district").has_school.sum(),
        "schools_within_800m": sd.groupby("district_poly").exposed.sum(),
        "children_5_14_within_800m": kids,
    }).fillna(0).astype(int).sort_values("children_5_14_within_800m", ascending=False)
    tab["layer"] = label
    total_kids = tab.children_5_14_within_800m.sum()
    top3 = tab.children_5_14_within_800m.head(3).sum() / max(total_kids, 1)
    summ = pd.Series({
        "layer": label,
        "kilns": len(kilns),
        "H1_kilns_with_school_within_800m_pct": round(100 * kiln_has_school.mean(), 1),
        "schools_within_800m": int(school_exposed.sum()),
        "schools_within_800m_pct": round(100 * school_exposed.mean(), 1),
        "children_5_14_within_800m": int(total_kids),
        "H2_top3_district_share_pct": round(100 * top3, 1),
        "top3_districts": ", ".join(tab.index[:3]),
    })
    return tab, summ


def main() -> None:
    ee.Initialize(project="geosync-448701")
    det = gpd.read_file(ROOT / "data" / "kilns" / "detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
    sch = gpd.read_file(ROOT / "data" / "schools" / "ncr_schools_32643.gpkg")
    sch = sch[sch.use_strict][["schcd", "geometry"]].reset_index(drop=True)
    dist = gpd.read_file(ROOT / "data" / "boundaries" / "ncr_districts_32643.gpkg")
    dist["district"] = dist.district.str.replace(" (pre-2023)", "", regex=False)

    tabs, summs = [], []
    # non-kiln heat sources (airports, refineries, year-round heat) removed: nonkiln_flag.py
    removed = det.fires & ~det.kiln_final
    for label, k in (("lower: firing-verified", det[det.kiln_final]), ("upper: all filtered", det[~removed])):
        print(f"running {label} ({len(k)} kilns)")
        t, s = run(k.reset_index(drop=True), sch, dist, label)
        tabs.append(t); summs.append(s)
    pd.concat(tabs).to_csv(ROOT / "outputs" / "tables" / "exposure_by_district.csv")
    S = pd.DataFrame(summs).set_index("layer")
    S.to_csv(ROOT / "outputs" / "tables" / "exposure_summary.csv")
    print(S.T.to_string())
    print("\nTop districts (lower layer):")
    print(tabs[0].drop(columns="layer").head(8).to_string())


if __name__ == "__main__":
    main()
