"use client";
// The single-page dashboard: map in the centre, overview on the left, details on the right.
// One piece of state, `sel` (what is selected), is written by the map, search, charts and lists,
// and read by the right panel and the map highlight. Nothing navigates away.
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DistrictProps, KilnRow, School, SchoolsCompact, Summary, Wayback } from "@/lib/data";
import { BASE, STATUS_LABEL, expandSchools, fmt, fmtRound, loadJSON } from "@/lib/data";
import { distM, googleSat, waybackLink } from "@/lib/geo";
import { supabase } from "@/lib/supabase";
import type { Basemap, GoogleRow, Layers, Pick } from "./MapView";

const MapView = dynamic(() => import("./MapView"), { ssr: false });

type Sel = { kind: "district"; name: string } | { kind: "school"; school: School } | { kind: "kiln"; kiln: KilnRow } | { kind: "google"; row: GoogleRow } | null;
type Focus = { lat: number; lon: number; zoom?: number; bounds?: [[number, number], [number, number]] } | null;
type DistrictFeature = { properties: DistrictProps; geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon };

// thumbnails for the basemap switch: one Esri tile (zoom 11) over Baghpat, satellite and street versions
const THUMB_SAT = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/11/852/1463";
const THUMB_MAP = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/11/852/1463";
const STEPS = ["#FBE9DD", "#F6CDB3", "#EFA37E", "#E2734A", "#C24A22"];
const stepColor = (p: number | null) => (p === null ? "#DDE1DC" : STEPS[[2.6, 5.5, 9.7, 16.3, 999].findIndex((t) => p < t)]);

function bboxOf(g: GeoJSON.Polygon | GeoJSON.MultiPolygon): [[number, number], [number, number]] {
  const polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
  let w = 180, s = 90, e = -180, n = -90;
  for (const p of polys) for (const [x, y] of p[0]) { w = Math.min(w, x); e = Math.max(e, x); s = Math.min(s, y); n = Math.max(n, y); }
  return [[w, s], [e, n]];
}

function downloadCSV(name: string, head: string[], rows: (string | number)[][]) {
  const esc = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`;
  const blob = new Blob([[head.join(","), ...rows.map((r) => r.map(esc).join(","))].join("\n")], { type: "text/csv" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click(); URL.revokeObjectURL(a.href);
}

// ---------- small presentational pieces ----------
function Stat({ n, label, accent }: { n: string; label: string; accent?: boolean }) {
  return (
    <div style={{ background: "var(--soft)", borderRadius: 10, padding: "10px 12px" }}>
      <div className="mono" style={{ fontSize: 20, fontWeight: 500, color: accent ? "var(--kiln)" : undefined }}>{n}</div>
      <div style={{ fontSize: 12, color: "var(--muted)" }}>{label}</div>
    </div>
  );
}
function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return <section style={{ background: "#fff", borderRadius: 12, padding: "14px 16px", ...style }}>{children}</section>;
}
function Dot({ c, ring }: { c: string; ring?: boolean }) {
  return <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 10, marginRight: 8, verticalAlign: "-1px",
                        background: ring ? "transparent" : c, border: ring ? `2px solid ${c}` : "none", boxSizing: "border-box" }} />;
}
function Row({ onClick, left, sub, right, rightAccent }: { onClick: () => void; left: string; sub?: string; right: string; rightAccent?: boolean }) {
  return (
    <li>
      <button onClick={onClick} className="w-full text-left" style={{ display: "flex", gap: 10, alignItems: "baseline", padding: "8px 2px", borderBottom: "1px solid #EEF0EE" }}>
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={{ display: "block", fontSize: 14, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{left}</span>
          {sub && <span style={{ display: "block", fontSize: 12, color: "var(--muted)" }}>{sub}</span>}
        </span>
        <span className="mono" style={{ fontSize: 13, color: rightAccent ? "var(--kiln)" : "var(--fg)", whiteSpace: "nowrap" }}>{right}</span>
      </button>
    </li>
  );
}

export default function DashboardApp({ summary }: { summary: Summary }) {
  // ---------- data ----------
  const [kilns, setKilns] = useState<KilnRow[]>([]);
  const [schools, setSchools] = useState<School[]>([]);
  const [districts, setDistricts] = useState<GeoJSON.FeatureCollection | null>(null);
  const [wayback, setWayback] = useState<Wayback[]>([]);
  const [allSchools, setAllSchools] = useState<School[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([loadJSON<KilnRow[]>("kilns.json"), loadJSON<School[]>("schools_near.json"),
                 loadJSON<GeoJSON.FeatureCollection>("districts.json"), loadJSON<Wayback[]>("wayback.json")])
      .then(([k, s, d, w]) => { setKilns(k); setSchools(s); setDistricts(d); setWayback(w); })
      .catch((e) => setError(String(e.message || e)));
  }, []);
  // Rashmi's Google Maps scrape: local-only (dashboard/public/local/, git-ignored, stripped from the public build)
  // Two private sources, tried in order: (1) the local file on Rashmi's PC (dev only);
  // (2) the private Supabase bucket "private-layer", readable only by signed-in editors.
  // Anonymous visitors of the public site get neither, so the toggle never appears for them.
  const [googleSrc, setGoogleSrc] = useState<"" | "local" | "supabase">("");
  const [google, setGoogle] = useState<GoogleRow[] | undefined>(undefined);
  const [editorName, setEditorName] = useState("");
  useEffect(() => {
    fetch(`${BASE}/local/google_schools.json`, { method: "HEAD" }).then((r) => { if (r.ok) setGoogleSrc("local"); }).catch(() => {});
    if (!supabase) return;
    const check = async () => {
      const { data: { session } } = await supabase!.auth.getSession();
      if (!session) { setEditorName(""); return; }
      const { data } = await supabase!.from("editors").select("name").eq("user_id", session.user.id).maybeSingle();
      if (!data) return;
      setEditorName(data.name);
      setGoogleSrc((s) => s || "supabase");
    };
    check();
    const { data: sub } = supabase.auth.onAuthStateChange(() => { check(); });
    return () => sub.subscription.unsubscribe();
  }, []);
  const loadGoogle = useCallback(async () => {
    if (google) return;
    try {
      if (googleSrc === "local") { setGoogle(await (await fetch(`${BASE}/local/google_schools.json`)).json()); return; }
      if (googleSrc === "supabase" && supabase) {
        const { data, error } = await supabase.storage.from("private-layer").download("google_schools.json");
        if (error || !data) throw error;
        setGoogle(JSON.parse(await data.text()));
      }
    } catch { setGoogleSrc(""); }
  }, [google, googleSrc]);
  const loadAll = useCallback(() => {
    if (!allSchools) loadJSON<SchoolsCompact>("schools_all.json").then((c) => setAllSchools(expandSchools(c))).catch(() => {});
  }, [allSchools]);

  const dFeats = useMemo(() => (districts?.features ?? []) as unknown as DistrictFeature[], [districts]);
  const dRank = useMemo(() => dFeats.map((f) => f.properties).filter((d) => !d.excluded && d.pct !== null)
    .sort((a, b) => (b.pct ?? 0) - (a.pct ?? 0)), [dFeats]);

  // ---------- UI state ----------
  const [sel, setSel] = useState<Sel>(null);
  const [focus, setFocus] = useState<Focus>(null);
  const [layers, setLayers] = useState<Layers>({ districts: true, rings: true, kilns: true, schools: true, stopped: true });
  const [basemap, setBasemap] = useState<Basemap>("streets");
  const [labels, setLabels] = useState(true); // satellite + roads and place names (hybrid)
  const [listTab, setListTab] = useState<"schools" | "kilns">("schools");
  const [districtFilter, setDistrictFilter] = useState("");
  const [showAllDistricts, setShowAllDistricts] = useState(false);

  const selectDistrict = useCallback((name: string, fly = true) => {
    setSel({ kind: "district", name }); setDistrictFilter(name);
    const f = dFeats.find((x) => x.properties.name === name);
    if (fly && f) setFocus({ lat: 0, lon: 0, bounds: bboxOf(f.geometry) });
  }, [dFeats]);
  const selectSchool = useCallback((s: School, fly = true) => { setSel({ kind: "school", school: s }); if (fly) setFocus({ lat: s.lat, lon: s.lon, zoom: 15 }); }, []);
  const selectKiln = useCallback((k: KilnRow, fly = true) => { setSel({ kind: "kiln", kiln: k }); if (fly) setFocus({ lat: k[1], lon: k[2], zoom: 15 }); }, []);
  const onSelect = useCallback((p: Pick) => {
    if (p.google && !p.kiln && !p.school) { setSel({ kind: "google", row: p.google }); return; }
    if (p.kiln) selectKiln(p.kiln, false);
    else if (p.school) selectSchool(p.school, false);
    else if (p.district) selectDistrict(p.district, false);
  }, [selectKiln, selectSchool, selectDistrict]);
  const clearSel = () => { setSel(null); setDistrictFilter(""); setFocus({ lat: 28.75, lon: 77.25, zoom: 7.6 }); };

  const extra = useMemo(() => {
    if (sel?.kind === "school") return [{ lat: sel.school.lat, lon: sel.school.lon, label: sel.school.name, color: "#7c3aed" }];
    if (sel?.kind === "kiln") return [{ lat: sel.kiln[1], lon: sel.kiln[2], label: `Kiln #${sel.kiln[0]}`, color: "#7c3aed" }];
    if (sel?.kind === "google") return [{ lat: sel.row[0], lon: sel.row[1], label: sel.row[2], color: "#7c3aed" }];
    return [];
  }, [sel]);

  // ---------- search ----------
  const [q, setQ] = useState("");
  const [qOpen, setQOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (boxRef.current && !boxRef.current.contains(e.target as Node)) setQOpen(false); };
    document.addEventListener("mousedown", close); return () => document.removeEventListener("mousedown", close);
  }, []);
  const results = useMemo(() => {
    const t = q.trim().toLowerCase(); if (t.length < 2) return [];
    const out: { key: string; label: string; sub: string; go: () => void }[] = [];
    const kid = t.replace(/^#|^kiln\s*/, "");
    if (/^\d{1,5}$/.test(kid)) kilns.filter((k) => String(k[0]) === kid).forEach((k) =>
      out.push({ key: "k" + k[0], label: `Kiln #${k[0]}`, sub: `${k[7]} · ${STATUS_LABEL[String(k[4])]}`, go: () => selectKiln(k) }));
    dRank.filter((d) => d.name.toLowerCase().includes(t)).slice(0, 3).forEach((d) =>
      out.push({ key: "d" + d.name, label: d.name, sub: `District · ${d.pct}% of children within 800 m`, go: () => selectDistrict(d.name) }));
    const pool = allSchools ?? schools;
    const words = t.split(/\s+/);
    pool.filter((s) => words.every((w) => `${s.name} ${s.village} ${s.id}`.toLowerCase().includes(w)))
      .sort((a, b) => a.kiln_m - b.kiln_m).slice(0, 8).forEach((s) =>
        out.push({ key: "s" + s.id, label: s.name, sub: `${s.village}, ${s.district} · nearest kiln ${fmt(s.kiln_m)} m`, go: () => selectSchool(s) }));
    return out.slice(0, 10);
  }, [q, kilns, dRank, allSchools, schools, selectKiln, selectDistrict, selectSchool]);

  // ---------- derived lists ----------
  const kilnSchools = useCallback((k: KilnRow) => schools.map((s) => ({ s, d: distM(k[1], k[2], s.lat, s.lon) }))
    .filter((x) => x.d <= 800).sort((a, b) => a.d - b.d), [schools]);
  const schoolKilns = useCallback((s: School) => kilns.map((k) => ({ k, d: distM(s.lat, s.lon, k[1], k[2]) }))
    .filter((x) => x.d <= 2000).sort((a, b) => a.d - b.d), [kilns]);
  const listSchools = useMemo(() => schools.filter((s) => !districtFilter || s.district === districtFilter)
    .sort((a, b) => b.kilns_800m - a.kilns_800m || a.kiln_m - b.kiln_m), [schools, districtFilter]);
  const listKilns = useMemo(() => kilns.filter((k) => k[5] > 0 && (!districtFilter || k[7] === districtFilter))
    .sort((a, b) => a[6] - b[6]), [kilns, districtFilter]);

  const toggle = (k: keyof Layers) => setLayers((l) => ({ ...l, [k]: !l[k] }));
  const isWay = basemap !== "streets" && basemap !== "satellite";
  const restored = summary.children_range.find((r) => String(r.layer).startsWith("unreviewed"));
  const near = summary.stop_rates.find((r) => !r.near_school.startsWith("no"));
  const far = summary.stop_rates.find((r) => r.near_school.startsWith("no"));
  const stoppedPct = (100 * summary.stop_rates.reduce((a, r) => a + r.stopped, 0) / summary.stop_rates.reduce((a, r) => a + r.kilns, 0)).toFixed(1);

  // ---------- right panel ----------
  function renderRight() {
    if (sel?.kind === "district") {
      const d = dFeats.find((f) => f.properties.name === sel.name)?.properties;
      if (!d) return null;
      const rank = dRank.findIndex((x) => x.name === d.name) + 1;
      const ks = kilns.filter((k) => k[7] === d.name);
      const top = listSchools.slice(0, 30);
      return (
        <>
          <div>
            <div className="mono" style={{ fontSize: 12, color: "var(--muted)" }}>DISTRICT · {d.state.toUpperCase()}{rank ? ` · RANK ${rank} OF ${dRank.length}` : ""}</div>
            <h2 style={{ margin: "2px 0 0", fontSize: 26, fontWeight: 700, letterSpacing: "-0.02em" }}>{d.name}</h2>
            {d.pct !== null && <p style={{ margin: "4px 0 0", fontSize: 14 }}><b style={{ color: "var(--kiln)" }}>{d.pct}% of children</b> aged 5–14 ({fmt(d.children_exposed)} of {fmt(d.children_total)}) live within 800 m of a firing kiln.</p>}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 8 }}>
            <Stat n={fmt(d.kilns)} label="firing kilns" />
            <Stat n={fmt(d.kilns_with_school)} label="with a school ≤ 800 m" accent />
            <Stat n={fmt(d.schools)} label="schools inside 800 m" />
            <Stat n={fmt(ks.filter((k) => k[4] === 0).length)} label="stopped by 2025–26" />
          </div>
          <button className="btn btn-primary" style={{ justifyContent: "center", height: 40, background: "var(--ink)", borderColor: "var(--ink)" }}
                  onClick={() => downloadCSV(`kilnwatch_${d.name.replace(/\s+/g, "_")}_kilns_near_schools.csv`,
                    ["kiln_id", "lat", "lon", "status_2025_26", "fired_pct_2023_24", "nearest_school_m", "schools_within_800m"],
                    ks.filter((k) => k[5] > 0).map((k) => [k[0], k[1], k[2], STATUS_LABEL[String(k[4])], k[3], k[6],
                      kilnSchools(k).map((x) => `${x.s.name} (${Math.round(x.d)} m)`).join("; ")]))}>
            Download inspection list ({fmt(d.kilns_with_school)} kilns)
          </button>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 2 }}>Schools with the most kilns nearby</div>
            <ul>{top.map((s) => <Row key={s.id} onClick={() => selectSchool(s)} left={s.name} sub={s.village} right={`${s.kilns_800m} · ${fmt(s.kiln_m)} m`} rightAccent />)}</ul>
          </div>
        </>
      );
    }
    if (sel?.kind === "school") {
      const s = sel.school, ks = schoolKilns(s), inside = ks.filter((x) => x.d <= 800);
      return (
        <>
          <div>
            <div className="mono" style={{ fontSize: 12, color: "var(--muted)" }}>SCHOOL · UDISE {s.id}</div>
            <h2 style={{ margin: "2px 0 0", fontSize: 22, fontWeight: 700, lineHeight: 1.2 }}>{s.name}</h2>
            <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 2 }}>{s.village}, {s.district} · {s.cat} · {s.mgmt}</div>
          </div>
          {inside.length > 0
            ? <div style={{ background: "#FBEDE6", borderRadius: 10, padding: 12, fontSize: 14, color: "#5E3020" }}><b style={{ color: "#8A2C0D" }}>Inside the 800 m siting distance.</b> {inside.length} firing kiln{inside.length > 1 ? "s" : ""} within 800 m; nearest {fmt(Math.round(inside[0].d))} m.</div>
            : <div style={{ background: "var(--soft)", borderRadius: 10, padding: 12, fontSize: 14 }}>No firing kiln within 800 m{ks[0] ? ` (nearest ${fmt(Math.round(ks[0].d))} m)` : ""}.</div>}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 8 }}>
            <Stat n={String(inside.length)} label="kilns within 800 m" accent={inside.length > 0} />
            <Stat n={ks[0] ? `${fmt(Math.round(ks[0].d))} m` : "> 2 km"} label="to the nearest kiln" />
          </div>
          {ks.length > 0 && <div>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 2 }}>Kilns within 2 km</div>
            <ul>{ks.slice(0, 15).map(({ k, d }) => <Row key={k[0]} onClick={() => selectKiln(k)} left={`Kiln #${k[0]}`} sub={`${STATUS_LABEL[String(k[4])]} · fired in ${k[3]}% of scenes`} right={`${fmt(Math.round(d))} m`} rightAccent={d <= 800} />)}</ul>
          </div>}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <a className="btn" href={googleSat(s.lat, s.lon)} target="_blank" rel="noopener">Google satellite ↗</a>
            <a className="btn" href={`https://www.google.com/maps/search/${encodeURIComponent(s.name + ", " + s.village)}/@${s.lat},${s.lon},16z`} target="_blank" rel="noopener">Search name ↗</a>
          </div>
          <p className="note">Official UDISE+ register location, not field-verified. <Link className="link" href="/edit/">Report a problem</Link></p>
        </>
      );
    }
    if (sel?.kind === "kiln") {
      const k = sel.kiln, ss = kilnSchools(k);
      return (
        <>
          <div>
            <div className="mono" style={{ fontSize: 12, color: "var(--muted)" }}>BRICK KILN · {(k[7] || "").toUpperCase()}</div>
            <h2 style={{ margin: "2px 0 0", fontSize: 26, fontWeight: 700 }}>Kiln #{k[0]}</h2>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 8 }}>
            <Stat n={`${k[3]}%`} label="scenes hot, 2023–24" />
            <Stat n={STATUS_LABEL[String(k[4])]} label="in 2025–26" />
            <Stat n={String(ss.length)} label="schools within 800 m" accent={ss.length > 0} />
            <Stat n={`${fmt(ss[0] ? Math.round(ss[0].d) : k[6])} m`} label="to the nearest school" />
          </div>
          {ss.length > 0 && <div>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 2 }}>Schools inside 800 m</div>
            <ul>{ss.map(({ s, d }) => <Row key={s.id} onClick={() => selectSchool(s)} left={s.name} sub={s.village} right={`${fmt(Math.round(d))} m`} rightAccent />)}</ul>
          </div>}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <a className="btn" href={googleSat(k[1], k[2])} target="_blank" rel="noopener">Google satellite ↗</a>
            <a className="btn" href={waybackLink(k[1], k[2])} target="_blank" rel="noopener">Esri Wayback ↗</a>
          </div>
          <p className="note">Firing from a shortwave-infrared heat test on Sentinel-2; checked by eye on high-resolution imagery.</p>
        </>
      );
    }
    if (sel?.kind === "google") {
      const [lat, lon, title, category, cls, reviews] = sel.row;
      const regNear = (allSchools ?? schools).map((s) => ({ s, d: distM(lat, lon, s.lat, s.lon) })).sort((a, b) => a.d - b.d)[0];
      const kNear = kilns.map((k) => ({ k, d: distM(lat, lon, k[1], k[2]) })).sort((a, b) => a.d - b.d);
      const inside = kNear.filter((x) => x.d <= 800).length;
      return (
        <>
          <div>
            <div className="mono" style={{ fontSize: 12, color: "#15803D" }}>GOOGLE MAPS LISTING · YOUR SCRAPE · PRIVATE</div>
            <h2 style={{ margin: "2px 0 0", fontSize: 22, fontWeight: 700, lineHeight: 1.2 }}>{title || "Unnamed place"}</h2>
            <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 2 }}>{[category, cls].filter(Boolean).join(" · ")}{reviews ? ` · ${fmt(reviews)} reviews` : ""}</div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 8 }}>
            <Stat n={String(inside)} label="kilns within 800 m" accent={inside > 0} />
            <Stat n={kNear[0] ? `${fmt(Math.round(kNear[0].d))} m` : "-"} label="to the nearest kiln" />
          </div>
          {regNear && <div style={{ background: "var(--soft)", borderRadius: 10, padding: 12, fontSize: 14 }}>
            Nearest <b>register</b> school: <button className="link" onClick={() => selectSchool(regNear.s)}>{regNear.s.name}</button>, {fmt(Math.round(regNear.d))} m away.
            {!allSchools && <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>(searched near-kiln register schools only; use the search box once to load all)</div>}
          </div>}
          <p className="note">From your own Google Maps scrape, visible only on your PC or to signed-in editors. It is not counted in any result and is never part of the public files (Google Maps content may not be republished).</p>
        </>
      );
    }
    // nothing selected: ranked lists
    const rows = listTab === "schools" ? listSchools : listKilns;
    return (
      <>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>{districtFilter || "All NCR (outside Delhi)"}</h2>
          <p style={{ margin: "2px 0 0", fontSize: 13, color: "var(--muted)" }}>Click anything on the map, or pick from the lists.</p>
        </div>
        <div role="tablist" style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0,1fr))", background: "var(--soft)", borderRadius: 10, padding: 3 }}>
          {([["schools", `Schools · ${listSchools.length}`], ["kilns", `Kilns near schools · ${listKilns.length}`]] as const).map(([id, label]) => (
            <button key={id} role="tab" aria-selected={listTab === id} onClick={() => setListTab(id)}
                    style={{ height: 34, borderRadius: 8, fontSize: 13, fontWeight: listTab === id ? 600 : 500,
                             background: listTab === id ? "#fff" : "transparent", boxShadow: listTab === id ? "0 1px 2px rgba(0,0,0,.12)" : "none",
                             color: listTab === id ? "var(--fg)" : "var(--muted)" }}>{label}</button>
          ))}
        </div>
        <ul style={{ flex: "1 1 auto", minHeight: 0, overflowY: "auto" }}>
          {listTab === "schools"
            ? (rows as School[]).slice(0, 200).map((s) => <Row key={s.id} onClick={() => selectSchool(s)} left={s.name} sub={`${s.village}, ${s.district}`} right={`${s.kilns_800m} kilns · ${fmt(s.kiln_m)} m`} rightAccent />)
            : (rows as KilnRow[]).slice(0, 200).map((k) => <Row key={k[0]} onClick={() => selectKiln(k)} left={`Kiln #${k[0]}`} sub={`${k[7]} · ${STATUS_LABEL[String(k[4])]}`} right={`${k[5]} school${k[5] > 1 ? "s" : ""} · ${fmt(k[6])} m`} rightAccent />)}
        </ul>
        <button className="btn" style={{ justifyContent: "center" }} onClick={() => listTab === "schools"
          ? downloadCSV("kilnwatch_schools_within_800m.csv", ["udise", "name", "village", "district", "kilns_within_800m", "nearest_kiln_m", "lat", "lon"],
              listSchools.map((s) => [s.id, s.name, s.village, s.district, s.kilns_800m, s.kiln_m, s.lat, s.lon]))
          : downloadCSV("kilnwatch_kilns_near_schools.csv", ["kiln_id", "district", "lat", "lon", "status_2025_26", "fired_pct_2023_24", "schools_within_800m", "nearest_school_m"],
              listKilns.map((k) => [k[0], k[7], k[1], k[2], STATUS_LABEL[String(k[4])], k[3], k[5], k[6]]))}>
          Download CSV ({fmt(rows.length)})
        </button>
      </>
    );
  }

  // ---------- layout ----------
  return (
    <div className="kw-app">
      <header className="kw-header">
        <button onClick={clearSel} style={{ display: "flex", alignItems: "center", gap: 10, color: "#fff", textAlign: "left" }} aria-label="KilnWatch: reset view">
          <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><rect x="3" y="12" width="20" height="11" rx="2" fill="none" stroke="#E9A07F" strokeWidth="2" /><path d="M8 12V4h4v8" fill="none" stroke="#E9A07F" strokeWidth="2" /><path d="M15 3c2 1 2 3 0 4" fill="none" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" /></svg>
          <span><span style={{ display: "block", fontWeight: 700, fontSize: 17, lineHeight: 1.1 }}>KilnWatch</span>
            <span style={{ display: "block", fontSize: 12, color: "#9AA3AB" }}>Brick kilns and schoolchildren · Delhi-NCR</span></span>
        </button>
        <div ref={boxRef} style={{ position: "relative", flex: "1 1 280px", maxWidth: 480, minWidth: 0 }}>
          <label htmlFor="kwq" className="sr-only">Search a school, village, district or kiln</label>
          <input id="kwq" type="search" value={q} placeholder="Search a school, village, district or kiln #" autoComplete="off"
                 onFocus={() => { setQOpen(true); loadAll(); }} onChange={(e) => { setQ(e.target.value); setQOpen(true); }}
                 onKeyDown={(e) => { if (e.key === "Enter" && results[0]) { results[0].go(); setQOpen(false); } if (e.key === "Escape") setQOpen(false); }}
                 style={{ width: "100%", height: 40, padding: "0 14px", borderRadius: 10, background: "#222930", border: "1px solid #39424B", color: "#fff", fontSize: 14 }} />
          {qOpen && results.length > 0 && (
            <ul style={{ position: "absolute", zIndex: 20, top: 44, left: 0, right: 0, background: "#fff", color: "var(--fg)", borderRadius: 10, boxShadow: "0 10px 30px rgba(0,0,0,.2)", padding: 4, maxHeight: 380, overflowY: "auto" }}>
              {results.map((r) => (
                <li key={r.key}><button onClick={() => { r.go(); setQOpen(false); }} className="w-full text-left" style={{ padding: "8px 10px", borderRadius: 8 }}>
                  <span style={{ display: "block", fontSize: 14, fontWeight: 500 }}>{r.label}</span>
                  <span style={{ display: "block", fontSize: 12, color: "var(--muted)" }}>{r.sub}</span>
                </button></li>
              ))}
            </ul>
          )}
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#C4CAD0" }}>District
          <select value={districtFilter} onChange={(e) => e.target.value ? selectDistrict(e.target.value) : clearSel()}
                  style={{ height: 38, padding: "0 10px", borderRadius: 8, background: "#222930", border: "1px solid #39424B", color: "#fff", fontSize: 14, fontWeight: 600 }}>
            <option value="">All NCR</option>
            {dRank.map((d) => <option key={d.name} value={d.name}>{d.name}</option>)}
          </select>
        </label>
        <span style={{ flex: "1 1 0" }} />
        <Link href="/method/" style={{ fontSize: 13, color: "#C4CAD0" }}>Method</Link>
        <Link href="/edit/" style={{ fontSize: 13, color: "#fff", border: "1px solid #39424B", borderRadius: 8, padding: "9px 12px" }}>{editorName ? `${editorName} · editor` : "Analyst sign-in"}</Link>
      </header>

      <aside className="kw-left" aria-label="Overview">
        <Card>
          <div style={{ fontSize: 12, color: "var(--muted)" }}>Children 5–14 within 800 m of a firing kiln</div>
          <div className="mono" style={{ fontSize: 32, fontWeight: 500, letterSpacing: "-0.02em", color: "var(--kiln)" }}>{fmtRound(summary.children_800m)}</div>
          <div style={{ fontSize: 12, color: "var(--muted)" }}>NCR outside Delhi{restored ? ` · range ${fmtRound(summary.children_800m)}–${fmtRound(Number(restored.children))}` : ""}</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 8, marginTop: 12 }}>
            <Stat n={fmt(summary.schools_800m)} label="schools within 800 m" />
            <Stat n={fmt(summary.kilns)} label="firing kilns" />
            <Stat n={`${summary.pct_kilns_with_school}%`} label="kilns with a school ≤ 800 m" />
            <Stat n={`${stoppedPct}%`} label="stopped by 2025–26" />
          </div>
        </Card>

        <Card>
          <div style={{ fontSize: 14, fontWeight: 600 }}>PM<sub>2.5</sub> limits in the air we breathe</div>
          <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 8 }}>24-hour average, micrograms of fine dust per cubic metre of air</div>
          {([["WHO guideline", 15, "var(--school)"], ["India limit (NAAQS)", 60, "var(--ink)"], ["Delhi-NCR winter days", 200, "var(--kiln)"]] as const).map(([l, v, c]) => (
            <div key={l} style={{ marginBottom: 6 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}><span>{l}</span><span className="mono">{v === 200 ? "often > 200" : v} µg/m³</span></div>
              <div style={{ height: 6, background: "var(--soft)", borderRadius: 3 }}><div style={{ width: `${(v / 200) * 100}%`, height: 6, background: c, borderRadius: 3 }} /></div>
            </div>
          ))}
          <dl style={{ fontSize: 12, color: "var(--muted)", margin: "8px 0 0", display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 8, rowGap: 2 }}>
            <dt className="mono">PM<sub>2.5</sub></dt><dd style={{ margin: 0 }}>Particulate matter: dust particles smaller than 2.5 micrometres</dd>
            <dt className="mono">µg/m³</dt><dd style={{ margin: 0 }}>Micrograms (millionths of a gram) per cubic metre of air</dd>
            <dt className="mono">NAAQS</dt><dd style={{ margin: 0 }}>National Ambient Air Quality Standards (India)</dd>
            <dt className="mono">CPCB</dt><dd style={{ margin: 0 }}>Central Pollution Control Board</dd>
            <dt className="mono">WHO</dt><dd style={{ margin: 0 }}>World Health Organization</dd>
          </dl>
          <p className="note" style={{ marginTop: 8 }}>Limits: CPCB National Ambient Air Quality Standards (2009); WHO Air Quality Guidelines (2021). The winter level is a typical monitor reading, not measured by this project. Our kiln figure ({fmt(Math.round(summary.emissions[0].pm25_t / 100) * 100)}–{fmt(Math.round(summary.emissions[1].pm25_t / 100) * 100)} t a season) is how much dust is <i>released</i>, not how much is in the air at a school, so it cannot be compared with these limits directly.</p>
        </Card>

        <Card>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Map layers</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 14 }}>
            {([["kilns", "Firing kilns", <Dot key="k" c="var(--kiln)" />], ["stopped", "Include stopped kilns", <Dot key="s" c="var(--kiln-stopped)" />],
               ["rings", "800 m rings", <Dot key="r" c="var(--kiln)" ring />], ["schools", "Schools within 800 m", <Dot key="sc" c="var(--school)" />],
               ["districts", "District shading", <Dot key="d" c="#EFA37E" />],
               ...(googleSrc ? [["google", `Google Maps schools (your scrape, ${googleSrc === "local" ? "this PC" : "private"})`, <Dot key="g" c="#15803D" />]] : [])] as [keyof Layers, string, React.ReactNode][]).map(([k, l, icon]) => (
              <label key={k} style={{ display: "flex", alignItems: "center", gap: 8, minHeight: 26 }}>
                <input type="checkbox" checked={!!layers[k]} onChange={() => { if (k === "google") loadGoogle(); toggle(k); }} style={{ width: 16, height: 16, accentColor: "var(--ink)" }} />{icon}{l}
              </label>
            ))}
          </div>
          <div role="group" aria-label="Basemap" style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0,1fr))", background: "var(--soft)", borderRadius: 10, padding: 3, marginTop: 12 }}>
            {([["streets", "Streets"], ["satellite", "Satellite"], ["hybrid", "Both"]] as const).map(([id, label]) => {
              const on = id === "streets" ? basemap === "streets" : basemap !== "streets" && (id === "hybrid" ? labels : !labels);
              return (
                <button key={id} aria-pressed={on} title={id === "hybrid" ? "Satellite with roads and place names" : undefined}
                        onClick={() => { if (id === "streets") setBasemap("streets"); else { if (basemap === "streets") setBasemap("satellite"); setLabels(id === "hybrid"); } }}
                        style={{ height: 32, borderRadius: 8, fontSize: 13, fontWeight: 600, background: on ? "#fff" : "transparent", boxShadow: on ? "0 1px 2px rgba(0,0,0,.12)" : "none" }}>{label}</button>
              );
            })}
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, marginTop: 10 }}>Satellite year
            <select value={isWay ? basemap : ""} onChange={(e) => setBasemap(e.target.value || "satellite")}
                    style={{ flex: 1, height: 32, borderRadius: 8, border: "1px solid var(--line)", background: "#fff", padding: "0 8px" }}>
              <option value="">Latest</option>
              {wayback.map((w) => <option key={w.date} value={w.date}>{w.year} ({w.date})</option>)}
            </select>
          </label>
          <div style={{ marginTop: 12 }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, minmax(0,1fr))", gap: 2 }}>{STEPS.map((c) => <span key={c} style={{ height: 8, background: c }} />)}</div>
            <div className="mono" style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--muted)", marginTop: 3 }}><span>0%</span><span>2.6</span><span>5.5</span><span>9.7</span><span>16.3</span><span>32%</span></div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>District shading: % of children within 800 m</div>
          </div>
        </Card>

        <Card>
          <div style={{ fontSize: 14, fontWeight: 600 }}>Children exposed, by district</div>
          <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 8 }}>Click a district to zoom to it</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            {(showAllDistricts ? dRank : dRank.slice(0, 8)).map((d) => (
              <button key={d.name} onClick={() => selectDistrict(d.name)} aria-pressed={sel?.kind === "district" && sel.name === d.name}
                      style={{ display: "grid", gridTemplateColumns: "100px 1fr 40px", gap: 8, alignItems: "center", fontSize: 13, padding: "3px 4px", borderRadius: 6,
                               background: sel?.kind === "district" && sel.name === d.name ? "var(--soft)" : "transparent", textAlign: "left" }}>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: sel?.kind === "district" && sel.name === d.name ? 700 : 400 }}>{d.name}</span>
                <span style={{ height: 10, background: "#EEF0EE", borderRadius: 5 }}><span style={{ display: "block", height: 10, borderRadius: 5, width: `${(100 * (d.pct ?? 0)) / (dRank[0]?.pct || 1)}%`, background: stepColor(d.pct) }} /></span>
                <span className="mono" style={{ textAlign: "right" }}>{d.pct}</span>
              </button>
            ))}
          </div>
          <button className="link" style={{ fontSize: 13, marginTop: 6 }} onClick={() => setShowAllDistricts(!showAllDistricts)}>{showAllDistricts ? "Show top 8" : `Show all ${dRank.length}`}</button>
        </Card>

        {near && far && <Card>
          <div style={{ fontSize: 14, fontWeight: 600 }}>Are kilns near schools closing?</div>
          <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 8 }}>Kilns stopped by 2025–26</div>
          {[[near, "School ≤ 800 m", "var(--kiln)"], [far, "No school nearby", "var(--kiln-stopped)"]].map(([r, l, c]) => {
            const rr = r as typeof near;
            return (
              <div key={l as string} style={{ fontSize: 13, marginBottom: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}><span>{l as string}</span><span className="mono">{rr.stop_rate_pct}%</span></div>
                <div style={{ height: 8, background: "#EEF0EE", borderRadius: 4, marginTop: 3 }}><div style={{ height: 8, borderRadius: 4, width: `${rr.stop_rate_pct * 5}%`, background: c as string }} /></div>
              </div>
            );
          })}
          <p style={{ margin: "6px 0 0", fontSize: 12 }}><b>No difference</b> ({summary.stop_test.diff_pp} points, 95% CI {summary.stop_test.ci[0]} to {summary.stop_test.ci[1]}).</p>
        </Card>}
        <p style={{ fontSize: 11, color: "var(--muted)", padding: "0 4px" }}>Kilns: Sentinel-2, every kiln checked by eye (analyst audit {summary.audit.active}/{summary.audit.random_kilns - summary.audit.unclear} working). Schools: UDISE+ register. Children: WorldPop 2020. Analysis: Rashmi Sinha. Data {summary.built}.</p>
      </aside>

      <main className="kw-map" aria-label="Map">
        <MapView kilns={kilns} schools={schools} districts={districts} wayback={wayback} basemap={basemap} layers={layers} labels={labels} google={google}
                 extra={extra} focus={focus} onSelect={onSelect} />
        {/* one-tap basemap switch, like the corner thumbnail in Google Maps: it previews the OTHER view */}
        <button onClick={() => { if (basemap === "streets") { setBasemap("satellite"); setLabels(true); } else setBasemap("streets"); }}
                aria-label={basemap === "streets" ? "Switch to satellite view" : "Switch to street map"}
                style={{ position: "absolute", left: 12, top: 12, zIndex: 5, width: 76, height: 76, padding: 0, borderRadius: 12, overflow: "hidden",
                         border: "3px solid #fff", boxShadow: "0 3px 12px rgba(0,0,0,.3)", background: "#DDE1DC" }}>
          <img alt="" src={basemap === "streets" ? THUMB_SAT : THUMB_MAP} style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
          <span style={{ position: "absolute", left: 0, right: 0, bottom: 0, padding: "3px 0", fontSize: 11, fontWeight: 700, color: "#fff",
                         background: "linear-gradient(transparent, rgba(0,0,0,.7))" }}>{basemap === "streets" ? "Satellite" : "Map"}</span>
        </button>
        {error && <div style={{ position: "absolute", top: 12, left: 12, background: "#fff", padding: 10, borderRadius: 8, color: "var(--kiln)" }}>{error}</div>}
        {!kilns.length && !error && <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", color: "var(--muted)" }}>Loading map data…</div>}
      </main>

      <aside className="kw-right" aria-label="Details">
        {sel && <button onClick={clearSel} style={{ alignSelf: "flex-start", fontSize: 13, color: "var(--muted)" }}>← All of NCR</button>}
        {renderRight()}
      </aside>
    </div>
  );
}
