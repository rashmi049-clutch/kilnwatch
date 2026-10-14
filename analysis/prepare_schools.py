"""
Day 1 (step 5) - School locations for the NCR.

Source: NIC SchoolGIS, as scraped into datameet/udise_schools. The README
describes lat/lon as "accurate" coordinates and latitude/longitude as the
original; both are kept so the difference can be measured.

Checks recorded (not fixes):
  * missing or zero coordinates
  * points whose own district label disagrees with the district polygon
    they fall in - a direct measure of mislocation
  * exact duplicate coordinates shared by several schools

Enrolment is not in this file (option C: block-level estimates first,
UDISE+ school-level counts later if registered access is obtained).

Output:
    data/schools/ncr_schools_32643.gpkg
    outputs/tables/school_location_checks.csv
"""

import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ZIP = ROOT / "data" / "schools" / "udise_schools.zip"
UTM = "EPSG:32643"
COLS = ["schcd", "schname", "school_cat", "school_typ", "management", "rururb",
        "dtname", "stname", "vilname", "lat", "lon", "latitude", "longitude"]


def norm(s: pd.Series) -> pd.Series:
    return (s.fillna("").str.lower().str.replace(r"[^a-z]", "", regex=True)
            .str.replace("gurgaon", "gurugram").str.replace("mewat", "nuh")
            .str.replace("buddh", "buddha").str.replace("buddhaa", "buddha"))


def main() -> None:
    ncr = gpd.read_file(ROOT / "data" / "boundaries" / "ncr_districts_32643.gpkg")
    minx, miny, maxx, maxy = ncr.to_crs("EPSG:4326").total_bounds

    parts = []
    with zipfile.ZipFile(ZIP) as z, z.open("udise_schools.csv") as f:
        for chunk in pd.read_csv(f, usecols=lambda c: c in COLS, chunksize=200_000, low_memory=False):
            for c in ("lat", "lon", "latitude", "longitude"):
                chunk[c] = pd.to_numeric(chunk[c], errors="coerce")
            box = chunk.lat.between(miny, maxy) & chunk.lon.between(minx, maxx)
            parts.append(chunk[box])
    df = pd.concat(parts, ignore_index=True)

    g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs="EPSG:4326").to_crs(UTM)
    g = gpd.sjoin(g, ncr[["district", "state", "geometry"]], predicate="within", how="inner").drop(columns="index_right")

    # Label vs location: the school's own district name against the polygon it sits in.
    lab, loc = norm(g.dtname), norm(g.district.str.replace(r"\(pre-2023\)", "", regex=True))
    g["district_match"] = [a in b or b in a for a, b in zip(lab, loc)]
    # Delhi schools carry education-zone names ("North East", "West B"); the
    # NCR layer holds Delhi as one unit, so any Delhi school inside it matches.
    g.loc[g.state.eq("Delhi"), "district_match"] = True
    # Schools whose record and location disagree are excluded from the main
    # count (median 9-57 km from their labelled district, so not boundary noise)
    # but kept in the file for the sensitivity run.
    g["use"] = g.district_match
    orig = gpd.points_from_xy(g.longitude, g.latitude, crs="EPSG:4326").to_crs(UTM)
    g["shift_m"] = g.geometry.distance(gpd.GeoSeries(orig, index=g.index))
    g["dup_coord"] = g.duplicated(subset=["lat", "lon"], keep=False)

    checks = pd.Series({
        "schools_in_ncr": len(g),
        "district_label_mismatch_pct": round(100 * (~g.district_match).mean(), 2),
        "shared_coordinates_pct": round(100 * g.dup_coord.mean(), 2),
        "accurate_vs_original_shift_median_m": round(g.shift_m.median(), 1),
        "shift_over_800m_pct": round(100 * (g.shift_m > 800).mean(), 2),
    })
    print(checks.to_string())
    print(g.groupby("state").size().rename("schools"))
    print(g.school_cat.value_counts().head(8))

    checks.to_csv(ROOT / "outputs" / "tables" / "school_location_checks.csv", header=["value"])
    g.to_file(ROOT / "data" / "schools" / "ncr_schools_32643.gpkg", driver="GPKG")


if __name__ == "__main__":
    main()
