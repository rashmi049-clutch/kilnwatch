"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { STATUS_LABEL, fmt } from "@/lib/data";
import { googleSat } from "@/lib/geo";

export type KilnNear = { id: number; lat: number; lon: number; district: string; firing: number; status: number;
                         n: number; nearest_m: number; schools: string[] };

type Key = "nearest_m" | "n" | "district" | "firing";

export default function KilnTable({ rows }: { rows: KilnNear[] }) {
  const [district, setDistrict] = useState("");
  const [onlyFiring, setOnlyFiring] = useState(false);
  const [sort, setSort] = useState<Key>("nearest_m");
  const districts = useMemo(() => [...new Set(rows.map((r) => r.district).filter(Boolean))].sort(), [rows]);
  const shown = useMemo(() => rows
    .filter((r) => (!district || r.district === district) && (!onlyFiring || r.status !== 0))
    .sort((a, b) => sort === "district" ? a.district.localeCompare(b.district) || a.nearest_m - b.nearest_m
                  : sort === "nearest_m" ? a.nearest_m - b.nearest_m : (b[sort] as number) - (a[sort] as number)),
    [rows, district, onlyFiring, sort]);

  function download() {
    const esc = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`;
    const head = ["kiln_id", "lat", "lon", "district", "fired_pct_scenes_2023_24", "status_2025_26", "schools_within_800m", "nearest_school_m", "schools"];
    const lines = shown.map((r) => [r.id, r.lat, r.lon, r.district, r.firing, STATUS_LABEL[String(r.status)], r.n, r.nearest_m, r.schools.join("; ")].map(esc).join(","));
    const blob = new Blob([[head.join(","), ...lines].join("\n")], { type: "text/csv" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = `kilnwatch_kilns_near_schools${district ? "_" + district.replace(/\s+/g, "_") : ""}.csv`; a.click();
    URL.revokeObjectURL(a.href);
  }

  const th = (k: Key, label: string, num = false) => (
    <th className={num ? "num" : ""}><button onClick={() => setSort(k)} style={{ fontWeight: sort === k ? 600 : 500 }}>{label}{sort === k ? " ↓" : ""}</button></th>
  );
  return (
    <div className="panel flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <select className="input" style={{ width: "auto" }} value={district} onChange={(e) => setDistrict(e.target.value)} aria-label="District">
          <option value="">All districts</option>{districts.map((d) => <option key={d}>{d}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={onlyFiring} onChange={() => setOnlyFiring(!onlyFiring)} />Exclude kilns stopped by 2025–26</label>
        <span className="text-sm muted">{shown.length} kilns</span>
        <button className="btn ml-auto" onClick={download}>Download CSV</button>
      </div>
      <div className="overflow-x-auto">
        <table className="tbl">
          <thead><tr><th>Kiln</th>{th("district", "District")}{th("nearest_m", "Nearest school", true)}{th("n", "Schools ≤800 m", true)}
            {th("firing", "Fired 2023–24", true)}<th>2025–26</th><th>Schools inside 800 m</th></tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id}>
                <td><Link className="link" href={`/map/?lat=${r.lat}&lon=${r.lon}&z=15&label=${encodeURIComponent("Kiln #" + r.id)}`}>#{r.id}</Link>
                  <div className="text-[12px]"><a className="muted underline" href={googleSat(r.lat, r.lon)} target="_blank" rel="noopener">satellite ↗</a></div></td>
                <td>{r.district}</td>
                <td className="num">{fmt(r.nearest_m)} m</td>
                <td className="num">{r.n}</td>
                <td className="num">{r.firing}%</td>
                <td>{STATUS_LABEL[String(r.status)]}</td>
                <td className="text-[13px]" style={{ minWidth: 260 }}>{r.schools.slice(0, 3).join(" · ")}{r.schools.length > 3 ? ` · +${r.schools.length - 3} more` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
