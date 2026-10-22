"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { KilnRow, School, SchoolsCompact } from "@/lib/data";
import { STATUS_LABEL, expandSchools, fmt, loadJSON } from "@/lib/data";
import { distM, googleSat } from "@/lib/geo";

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();

export default function SchoolSearch() {
  const [all, setAll] = useState<School[] | null>(null);
  const [kilns, setKilns] = useState<KilnRow[]>([]);
  const [q, setQ] = useState("");
  const [district, setDistrict] = useState("");
  const [sel, setSel] = useState<School | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([loadJSON<SchoolsCompact>("schools_all.json"), loadJSON<KilnRow[]>("kilns.json")])
      .then(([c, k]) => { setAll(expandSchools(c)); setKilns(k); })
      .catch((e) => setError(String(e.message || e)));
  }, []);

  const districts = useMemo(() => (all ? [...new Set(all.map((s) => s.district))].sort() : []), [all]);
  const hits = useMemo(() => {
    if (!all) return [];
    const words = norm(q).split(" ").filter(Boolean);
    if (!words.length && !district) return [];
    return all.filter((s) => (!district || s.district === district) &&
      words.every((w) => norm(`${s.name} ${s.village} ${s.id}`).includes(w)))
      .sort((a, b) => a.kiln_m - b.kiln_m).slice(0, 60);
  }, [all, q, district]);

  const nearKilns = useMemo(() => {
    if (!sel) return [];
    return kilns.map((k) => ({ k, d: distM(sel.lat, sel.lon, k[1], k[2]) }))
      .filter((x) => x.d <= 2000).sort((a, b) => a.d - b.d).slice(0, 12);
  }, [sel, kilns]);

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1.1fr]">
      <div className="panel flex flex-col gap-3">
        <label className="text-sm muted" htmlFor="q">School name, village or UDISE code</label>
        <input id="q" className="input" placeholder="e.g. Saroorpur, Aryan Public, 9080101413" value={q}
               onChange={(e) => setQ(e.target.value)} autoComplete="off" />
        <select className="input" value={district} onChange={(e) => setDistrict(e.target.value)} aria-label="District">
          <option value="">All districts</option>
          {districts.map((d) => <option key={d}>{d}</option>)}
        </select>
        {error && <p className="text-sm" style={{ color: "var(--kiln)" }}>{error}</p>}
        {!all && !error && <p className="text-sm muted">Loading {"~29,000"} schools…</p>}
        {all && (q || district) && <p className="text-[12px] muted">{hits.length === 60 ? "First 60 matches" : `${hits.length} matches`}, nearest to a kiln first</p>}
        <ul className="flex flex-col">
          {hits.map((s) => (
            <li key={s.id}>
              <button onClick={() => setSel(s)} className="w-full text-left py-2 px-1 text-sm"
                      style={{ borderBottom: "1px solid var(--line)", background: sel?.id === s.id ? "var(--bg)" : "transparent" }}>
                <div className="font-medium">{s.name}</div>
                <div className="muted text-[12px]">{s.village}, {s.district} ·{" "}
                  <span style={{ color: s.kiln_m <= 800 ? "var(--school-near)" : undefined, fontWeight: s.kiln_m <= 800 ? 600 : 400 }}>
                    nearest kiln {fmt(s.kiln_m)} m
                  </span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="panel">
        {!sel ? (
          <p className="muted text-sm">Pick a school to see the kilns around it.</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div>
              <div className="h2" style={{ marginBottom: 2 }}>{sel.name}</div>
              <div className="text-sm muted">{sel.village}, {sel.district}, {sel.state} · UDISE {sel.id}</div>
              <div className="text-sm muted">{sel.cat} · {sel.mgmt} · {sel.rural ? "rural" : "urban"}</div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="panel" style={{ padding: 12 }}>
                <div className="kpi-num" style={{ color: sel.kilns_800m ? "var(--school-near)" : undefined }}>{sel.kilns_800m}</div>
                <div className="kpi-label">firing kilns within 800 m</div>
              </div>
              <div className="panel" style={{ padding: 12 }}>
                <div className="kpi-num">{fmt(sel.kiln_m)} m</div>
                <div className="kpi-label">to the nearest kiln</div>
              </div>
            </div>
            <p className="text-sm">
              {sel.kilns_800m
                ? <>This school is <b>inside</b> the 800 m distance the Central Pollution Control Board sets for kilns near schools.</>
                : <>No firing kiln within 800 m.</>}
            </p>
            {nearKilns.length > 0 && (
              <table className="tbl">
                <thead><tr><th>Kiln</th><th className="num">Distance</th><th>2025–26</th><th className="num">Fired 2023–24</th></tr></thead>
                <tbody>
                  {nearKilns.map(({ k, d }) => (
                    <tr key={k[0]}>
                      <td><Link className="link" href={`/map/?lat=${k[1]}&lon=${k[2]}&label=${encodeURIComponent("Kiln #" + k[0])}`}>#{k[0]}</Link></td>
                      <td className="num" style={{ color: d <= 800 ? "var(--school-near)" : undefined }}>{fmt(Math.round(d))} m</td>
                      <td>{STATUS_LABEL[String(k[4])]}</td>
                      <td className="num">{k[3]}% of scenes</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="flex flex-wrap gap-2">
              <Link className="btn" href={`/map/?lat=${sel.lat}&lon=${sel.lon}&z=15&label=${encodeURIComponent(sel.name)}`}>Show on map</Link>
              <a className="btn" href={googleSat(sel.lat, sel.lon)} target="_blank" rel="noopener">Google satellite ↗</a>
            </div>
            <p className="note">The school point is its location in the official UDISE+ register, which is not field-verified: an analyst check
              found that a share of register points near kilns sit tens to hundreds of metres from the building. Distances are therefore approximate.</p>
          </div>
        )}
      </div>
    </div>
  );
}
