"""
Step 25 - How many firing kilns did the map miss? (completeness-corrected range)

The headline layer (3,057 kilns) is a floor. The obvious correction - divide by
detector recall (0.62) and firing-test sensitivity (0.76) - is REJECTED: both
figures are measured against SentinelKilnDB, which includes idle and relict
kilns. The detector misses many of those and the firing test rejects them, so
dividing by both corrects twice for the same kilns (3,057 x 0.91 / 0.47 ~ 5,900,
more firing kilns than SentinelKilnDB holds in total). Kept here as a
documented negative result.

Method adopted: treat SentinelKilnDB as a second, independently made list of
the same kilns and compare the two lists directly.

1. Heat-test every SentinelKilnDB NCR kiln with the same firing test as the map
   (firing_verify.hot_image, threshold 0.12) -> the firing reference list.
2. Match map kilns to firing reference kilns one-to-one (greedy, nearest first,
   <= 100 m) inside the area SentinelKilnDB covers (its 1.28 km patches).
3. Capture-recapture (Chapman estimator) on the two lists -> estimated number
   of firing kilns in the covered area, including those on neither list.
     high: map list taken as all true kilns
     low:  map list scaled by audited precision 0.91 (false kilns removed)
   Map kilns outside SentinelKilnDB coverage are scaled by the same ratio.
4. Exposure re-run (exposure.run, same schools and WorldPop) with the firing
   reference kilns the map missed added - located kilns, not modelled ones.
   Children low = this located-only figure. Children high = plus the kilns
   still unaccounted for (high estimate minus union), each given the marginal
   children-per-added-kiln measured in this step.
5. Outer bound: every SentinelKilnDB kiln added, firing or not.

Assumptions (stated in the report):
  - SentinelKilnDB kilns are real kilns (hand-labelled; precision taken as 1).
  - The two lists miss kilns independently. They do not fully: the detector was
    trained on SentinelKilnDB-style labels, so both tend to miss faint kilns.
    That biases the estimate LOW. The Chapman interval ignores this and is
    reported but not used as the uncertainty.
  - SentinelKilnDB labels come from scenes up to Feb 2025, so a few kilns built
    after the composite but firing by May 2024 count as "missed" (biases HIGH).

Output:
    data/kilns/kilndb_ncr_points_hot2324_32643.gpkg  reference kilns + hot_frac, matched flag
    outputs/tables/completeness_summary.csv
    outputs/tables/completeness_exposure.csv
"""

from pathlib import Path

import ee
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import box

import exposure as ex
import firing_verify as fv

ROOT = Path(__file__).resolve().parents[1]
UTM, THR, MATCH_M, PATCH_M = "EPSG:32643", 0.12, 100, 1280
PRECISION = 0.91          # audit 1 (Section: visual audit), 21/23
DELHI_SPILL = 529_301 - 528_161   # all-NCR minus excl-Delhi headline (exposure vs exposure_excl_delhi)


def greedy_match(A: np.ndarray, B: np.ndarray, r: float) -> tuple[set, set]:
    """One-to-one matching, nearest pairs first, within r metres."""
    d, j = cKDTree(B).query(A, k=8, distance_upper_bound=r)
    pairs = sorted((dd, i, jj) for i in range(len(A)) for dd, jj in zip(d[i], j[i]) if np.isfinite(dd))
    ua, ub = set(), set()
    for _, i, jj in pairs:
        if i not in ua and jj not in ub:
            ua.add(i); ub.add(jj)
    return ua, ub


def chapman(n1: float, n2: float, m: float) -> tuple[float, float]:
    N = (n1 + 1) * (n2 + 1) / (m + 1) - 1
    var = (n1 + 1) * (n2 + 1) * (n1 - m) * (n2 - m) / ((m + 1) ** 2 * (m + 2))
    return N, 1.96 * var ** 0.5


def xy(g: gpd.GeoDataFrame) -> np.ndarray:
    return np.c_[g.geometry.x, g.geometry.y]


def main() -> None:
    ee.Initialize(project="geosync-448701")
    det = gpd.read_file(ROOT / "data" / "kilns" / "detections_s2324_kiln_obb_ring_v1_best_filtered.gpkg")
    fin = det[det.kiln_final].reset_index(drop=True)
    ref = gpd.read_file(ROOT / "data" / "kilns" / "kilndb_ncr_points_32643.gpkg")
    print("sampling 2023-24 hot frequency at reference kilns")
    ref["hot_frac"] = fv.sample(fv.hot_image(), ref)
    ref["fires"] = ref.hot_frac >= THR

    # SentinelKilnDB coverage = union of its NCR patches
    idx = pd.read_parquet(ROOT / "data" / "kilns" / "kilndb_index.parquet")
    c = gpd.GeoSeries(gpd.points_from_xy(idx[idx.in_ncr].lon, idx[idx.in_ncr].lat), crs=4326).to_crs(UTM)
    h = PATCH_M / 2
    cov = gpd.GeoSeries([box(p.x - h, p.y - h, p.x + h, p.y + h) for p in c], crs=UTM).union_all()
    fin["in_cov"] = fin.within(cov)
    n_out = int((~fin.in_cov).sum())

    # capture-recapture inside coverage
    rf = ref[ref.fires].reset_index(drop=True)
    fc = fin[fin.in_cov].reset_index(drop=True)
    ua, _ = greedy_match(xy(fc), xy(rf), MATCH_M)
    n1, n2, m = len(fc), len(rf), len(ua)
    N_hi, ci = chapman(n1, n2, m)
    N_lo, _ = chapman(n1 * PRECISION, n2, m)
    k_hi = N_hi + n_out * N_hi / n1
    k_lo = N_lo + n_out * PRECISION * N_lo / (n1 * PRECISION)

    # all-kiln comparison (shows the double count in the naive correction)
    ua_all, _ = greedy_match(xy(fc), xy(ref), MATCH_M)

    # firing reference kilns the map missed (whole NCR), and all missed reference kilns
    _, ub_f = greedy_match(xy(fin), xy(rf), MATCH_M)
    _, ub_a = greedy_match(xy(fin), xy(ref), MATCH_M)
    missed_fire = rf.drop(index=list(ub_f))
    missed_all = ref.drop(index=list(ub_a))
    ref["matched_by_map"] = False
    ref.loc[ref.index[list(ub_a)], "matched_by_map"] = True
    ref.to_file(ROOT / "data" / "kilns" / "kilndb_ncr_points_hot2324_32643.gpkg", driver="GPKG")

    sch = gpd.read_file(ROOT / "data" / "schools" / "ncr_schools_32643.gpkg")
    sch = sch[sch.use_strict][["schcd", "geometry"]].reset_index(drop=True)
    dist = gpd.read_file(ROOT / "data" / "boundaries" / "ncr_districts_32643.gpkg")
    dist["district"] = dist.district.str.replace(" (pre-2023)", "", regex=False)

    layers = {
        "as detected": fin[["geometry"]],
        "+ missed firing reference kilns": pd.concat([fin[["geometry"]], missed_fire[["geometry"]]], ignore_index=True),
        "outer: + all missed reference kilns": pd.concat([fin[["geometry"]], missed_all[["geometry"]]], ignore_index=True),
    }
    rows, tabs = [], []
    for label, k in layers.items():
        print(f"exposure: {label} ({len(k)} kilns)")
        t, s = ex.run(gpd.GeoDataFrame(k, crs=UTM).reset_index(drop=True), sch, dist, label)
        tabs.append(t)
        rows.append({"layer": label, "kilns": len(k), "schools_800m": int(s.schools_within_800m),
                     "children_all_ncr": int(s.children_5_14_within_800m),
                     "children_excl_delhi_approx": int(s.children_5_14_within_800m) - DELHI_SPILL})
    E = pd.DataFrame(rows).set_index("layer")
    pd.concat(tabs).to_csv(ROOT / "outputs" / "tables" / "completeness_exposure.csv")

    base, plus = E.iloc[0], E.iloc[1]
    per_kiln = (plus.children_all_ncr - base.children_all_ncr) / (plus.kilns - base.kilns)
    # low: located kilns only, nothing modelled. (Modelling the low-case residual would also
    # require removing the ~9% false kilns' children, which cannot be done without knowing which.)
    kids_lo = plus.children_excl_delhi_approx
    kids_hi = plus.children_excl_delhi_approx + max(k_hi - plus.kilns, 0) * per_kiln

    S = pd.Series({
        "ref_kilns_total": len(ref),
        "ref_kilns_firing": len(rf),
        "ref_firing_pct": round(100 * ref.fires.mean(), 2),
        "map_kilns": len(fin),
        "map_kilns_in_ref_coverage": n1,
        "map_kilns_outside_coverage": n_out,
        "ref_coverage_km2": round(cov.area / 1e6),
        "matched_firing": m,
        "recall_vs_firing_ref": round(m / n2, 3),
        "share_map_confirmed_by_firing_ref": round(m / n1, 3),
        "share_map_confirmed_by_any_ref": round(len(ua_all) / n1, 3),
        "recall_vs_all_ref": round(len(ua_all) / len(ref), 3),
        "chapman_N_in_cov_high": round(N_hi), "chapman_ci95_halfwidth_not_used": round(ci),
        "chapman_N_in_cov_low": round(N_lo),
        "firing_kilns_est_low": round(k_lo), "firing_kilns_est_high": round(k_hi),
        "missed_firing_ref_kilns_added": len(missed_fire),
        "children_per_added_kiln": round(per_kiln, 1),
        "children_excl_delhi_est_low": round(kids_lo, -3), "children_excl_delhi_est_high": round(kids_hi, -3),
        "outer_kilns": int(E.iloc[2].kilns), "outer_children_excl_delhi": int(E.iloc[2].children_excl_delhi_approx),
        "outer_schools": int(E.iloc[2].schools_800m),
        "rejected_naive_kilns": round(len(fin) * PRECISION / (0.62 * 0.76)),
    })
    S.to_csv(ROOT / "outputs" / "tables" / "completeness_summary.csv", header=["value"])
    print(E.to_string()); print(S.to_string())


if __name__ == "__main__":
    main()
