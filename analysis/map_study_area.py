"""
Day 1 - Study area map with locator inset.

Main panel: the 25 NCR districts (Rajasthan at pre-2023 extents), shaded by
state. Inset: NCR within the surrounding states, so a reader who does not
know the region can place it. The inset shows neighbouring states only, not
a national outline, which avoids depicting disputed national boundaries.

Output:
    outputs/maps/00_study_area.png  (300 dpi)
"""

from datetime import date
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
BND = ROOT / "data" / "boundaries"
OUT = ROOT / "outputs" / "maps"
OUT.mkdir(parents=True, exist_ok=True)

UTM = "EPSG:32643"
INK, MUTED, HAIR = "#1c1f22", "#6b7278", "#c9ced2"
STATE_FILL = {"Delhi": "#c9d9e8", "Haryana": "#d5e5cf", "Uttar Pradesh": "#efe0c2", "Rajasthan": "#ecd3cc"}
STATE_EDGE = {"Delhi": "#2d5c88", "Haryana": "#4e6b3a", "Uttar Pradesh": "#8a5a00", "Rajasthan": "#9c3f2a"}
# Label offsets in metres where representative points crowd each other.
LABEL_NUDGE = {"Gautam Buddha Nagar": (6_000, -12_000), "Faridabad": (-2_000, 4_000),
               "Mahendragarh": (-4_000, 6_000)}
NEIGHBOURS = ["Delhi", "Haryāna", "Uttar Pradesh", "Rājasthān", "Punjab", "Himāchal Pradesh",
              "Uttarākhand", "Madhya Pradesh", "Chandīgarh"]


def main() -> None:
    d = gpd.read_file(BND / "ncr_districts_32643.gpkg")
    ncr = gpd.read_file(BND / "ncr_32643.gpkg")
    states = gpd.read_file(BND / "geoBoundaries-IND-ADM1_simplified.geojson").to_crs(UTM)
    states = states[states.shapeName.isin(NEIGHBOURS)]

    fig, ax = plt.subplots(figsize=(9, 10.5), dpi=300)
    for st, grp in d.groupby("state"):
        grp.plot(ax=ax, facecolor=STATE_FILL[st], edgecolor="white", linewidth=0.8, zorder=2)
    ncr.plot(ax=ax, facecolor="none", edgecolor=INK, linewidth=1.6, zorder=4)

    for _, r in d.iterrows():
        pt = r.geometry.representative_point()
        name = r.district.replace(" (pre-2023)", "*")
        dx, dy = LABEL_NUDGE.get(name, (0, 0))
        name = name.replace("Gautam Buddha Nagar", "Gautam\nBuddha Nagar")
        ax.annotate(name, xy=(pt.x + dx, pt.y + dy), ha="center", va="center", fontsize=6.3,
                    color=INK, zorder=5, linespacing=1.0)

    minx, miny, maxx, maxy = ncr.total_bounds
    w, h = maxx - minx, maxy - miny
    ax.set_xlim(minx - 0.05 * w, maxx + 0.05 * w)
    ax.set_ylim(miny - 0.08 * h, maxy + 0.04 * h)
    ax.set_aspect("equal")

    # Scale bar, 50 km in projected metres.
    x0, y0, L = minx + 0.02 * w, miny - 0.045 * h, 50_000
    for i, c in enumerate([INK, "white", INK, "white"]):
        ax.add_patch(plt.Rectangle((x0 + i * L / 4, y0), L / 4, 0.006 * h, facecolor=c, edgecolor=INK, lw=0.6, zorder=6))
    for v in (0, 25, 50):
        ax.annotate(f"{v}", xy=(x0 + v * 1000, y0), xytext=(0, -9), textcoords="offset points", ha="center", fontsize=6.5)
    ax.annotate("km", xy=(x0 + L, y0), xytext=(12, -9), textcoords="offset points", fontsize=6.5)

    # North arrow. UTM grid north; convergence here is under 1 degree.
    nx, ny = maxx - 0.02 * w, maxy - 0.02 * h
    ax.annotate("N", xy=(nx, ny), xytext=(nx, ny - 0.07 * h), ha="center", fontsize=10, weight="bold",
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.3))

    ax.legend(handles=[Patch(facecolor=STATE_FILL[s], edgecolor=STATE_EDGE[s], label=s) for s in STATE_FILL]
              + [Patch(facecolor="none", edgecolor=INK, lw=1.6, label="NCR boundary")],
              loc="lower right", fontsize=7.5, frameon=True, edgecolor=HAIR, title="State", title_fontsize=7.5)

    # Locator inset.
    ins = fig.add_axes([0.03, 0.70, 0.20, 0.16])
    states.plot(ax=ins, facecolor="#f2f3f4", edgecolor="#9aa2aa", linewidth=0.4)
    ncr.plot(ax=ins, facecolor="#9c3f2a", edgecolor="none", alpha=0.85)
    ins.set_xticks([]); ins.set_yticks([])
    for s in ins.spines.values():
        s.set_edgecolor(HAIR)
    ins.set_title("Location in north India", fontsize=6.5, color=MUTED, pad=2)

    ax.set_title("National Capital Region: study area", fontsize=14, weight="bold", loc="left", color=INK, pad=12)
    area = ncr.to_crs("+proj=aea +lat_1=12 +lat_2=32 +lat_0=22 +lon_0=80 +datum=WGS84 +units=m").area.iloc[0] / 1e6
    ax.annotate(
        f"CRS: EPSG:32643 (WGS 84 / UTM 43N)  ·  Area {area:,.0f} km² (equal-area)  ·  25 districts\n"
        "* Alwar and Bharatpur shown at pre-2023 extents, as in the NCR Planning Board definition\n"
        "Data: © OpenStreetMap contributors (ODbL); geoBoundaries (CC BY 4.0 / CC BY 2.5 IN)  ·  "
        f"Produced {date.today():%d %b %Y}, R. Sinha",
        xy=(0, -0.02), xycoords="axes fraction", fontsize=6.3, color=MUTED, va="top", linespacing=1.6)

    ax.set_axis_off()
    path = OUT / "00_study_area.png"
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
