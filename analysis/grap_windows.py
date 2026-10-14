"""
Phase 3 - GRAP Stage III/IV windows from CAQM orders.

Source: every GRAP order listed by CAQM (caqm.nic.in, GRAP > GRAP Orders),
read 28 Sep 2026 from the site's document index; the Stage III and IV
invoke/revoke orders are transcribed with their CAQM document ids in
data/grap/grap_orders_stage3_4.csv.

A day counts as a ban day when Stage III or IV is in force (Stage IV
includes Stage III). Resolution is one day: an order dated D is taken to
apply from D; one order (14.11.2024) states 08:00 next morning, which is
within that resolution.

Which GRAP stage closes brick kilns is taken from the GRAP schedule; this is
[to confirm against the schedule PDF] - see README.

Output:
    data/grap/grap_stage3_windows.csv
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    o = pd.read_csv(ROOT / "data" / "grap" / "grap_orders_stage3_4.csv", parse_dates=["order_date"])
    o = o.sort_values(["order_date", "action"], ascending=[True, False])
    on = {"III": False, "IV": False}
    windows, start = [], None
    for r in o.itertuples():
        was = on["III"] or on["IV"]
        on[r.stage] = r.action == "on"
        now = on["III"] or on["IV"]
        if now and not was:
            start = r.order_date
        elif was and not now:
            windows.append((start, r.order_date))
    w = pd.DataFrame(windows, columns=["start", "end"])
    w["days"] = (w.end - w.start).dt.days
    w["season"] = w.start.apply(lambda d: f"{d.year}-{str(d.year + 1)[2:]}" if d.month >= 7 else f"{d.year - 1}-{str(d.year)[2:]}")
    w.to_csv(ROOT / "data" / "grap" / "grap_stage3_windows.csv", index=False)
    print(w.to_string(index=False))
    print(w.groupby("season").days.agg(["count", "sum"]).rename(columns={"count": "windows", "sum": "ban_days"}))


if __name__ == "__main__":
    main()
