"""Figure for step 22: monthly kiln firing vs control background, Nov 2023 - Jun 2026."""
from pathlib import Path
import pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
k = pd.read_csv(ROOT / "outputs/tables/monthly_firing_ncr.csv", index_col=0)
c = pd.read_csv(ROOT / "outputs/tables/monthly_firing_controls.csv", index_col=0)
x = pd.PeriodIndex(k.index, freq="M").to_timestamp()
low = (k.median_clear_scenes <= 2).values           # months with <= 2 clear scenes per kiln
fig, ax = plt.subplots(figsize=(9, 3.6), dpi=200)
ax.axvline(pd.Timestamp("2025-01-01"), color="#888", lw=0.8, ls=":")
ax.text(pd.Timestamp("2025-01-08"), 66, "Sentinel-2C replaces 2A", fontsize=7, color="#666")
for y0, y1 in (("2024-07-01", "2024-10-01"), ("2025-07-01", "2025-10-01")):
    ax.axvspan(pd.Timestamp(y0), pd.Timestamp(y1), color="#4f7cac", alpha=0.08, lw=0)
ax.plot(x, 100 * k.mean_hot_share, color="#b3261e", lw=1.6, label="Firing kilns (3,290)")
ax.plot(x, 100 * c.mean_hot_share, color="#555", lw=1.2, ls="--", label="Random control points (1,000)")
ax.scatter(x[low], 100 * k.mean_hot_share[low], facecolor="white", edgecolor="#b3261e", s=22, zorder=3, label="≤ 2 clear images (unreliable)")
ax.scatter(x[~low], 100 * k.mean_hot_share[~low], color="#b3261e", s=12, zorder=3)
ax.set_ylabel("Clear images showing heat (%)", fontsize=8); ax.set_ylim(0, 72)
ax.tick_params(labelsize=7.5); ax.spines[["top", "right"]].set_visible(False)
ax.legend(fontsize=7, frameon=False, loc="upper right", ncol=3)
ax.set_title("Kiln firing by month, NCR · shaded = monsoon", fontsize=9, loc="left")
plt.tight_layout(); plt.savefig(ROOT / "outputs/figures/07_monthly_firing.png", facecolor="white")
print("ok")
