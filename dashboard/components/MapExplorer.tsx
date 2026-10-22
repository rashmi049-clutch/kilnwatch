"use client";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { KilnRow, School, Wayback } from "@/lib/data";
import { loadJSON } from "@/lib/data";
import type { Basemap, Layers } from "./MapView";

const MapView = dynamic(() => import("./MapView"), { ssr: false });

export function useMapData() {
  const [kilns, setKilns] = useState<KilnRow[]>([]);
  const [schools, setSchools] = useState<School[]>([]);
  const [districts, setDistricts] = useState<GeoJSON.FeatureCollection | null>(null);
  const [wayback, setWayback] = useState<Wayback[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([loadJSON<KilnRow[]>("kilns.json"), loadJSON<School[]>("schools_near.json"),
                 loadJSON<GeoJSON.FeatureCollection>("districts.json"), loadJSON<Wayback[]>("wayback.json")])
      .then(([k, s, d, w]) => { setKilns(k); setSchools(s); setDistricts(d); setWayback(w); })
      .catch((e) => setError(String(e.message || e)));
  }, []);
  return { kilns, schools, districts, wayback, error };
}

export function BasemapPicker({ value, onChange, wayback }: { value: Basemap; onChange: (b: Basemap) => void; wayback: Wayback[] }) {
  const isWay = value !== "streets" && value !== "satellite";
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button className="btn" aria-pressed={value === "streets"} onClick={() => onChange("streets")}>Streets</button>
      <button className="btn" aria-pressed={value === "satellite"} onClick={() => onChange("satellite")}>Satellite (latest)</button>
      <select className="input" style={{ width: "auto" }} aria-label="Satellite by year (Esri Wayback)"
              value={isWay ? value : ""} onChange={(e) => e.target.value && onChange(e.target.value)}>
        <option value="">Satellite by year…</option>
        {wayback.map((w) => <option key={w.date} value={w.date}>{w.year} ({w.date})</option>)}
      </select>
    </div>
  );
}

export function Legend() {
  const dot = (c: string, ring = false) => (
    <span style={{ display: "inline-block", width: 11, height: 11, borderRadius: 99, background: ring ? "transparent" : c,
                   border: ring ? `2px solid ${c}` : "1px solid #0003", marginRight: 6, verticalAlign: "-1px" }} />
  );
  return (
    <div className="text-[13px] leading-6">
      <div>{dot("var(--kiln)")}Kiln, firing (2023–24)</div>
      <div>{dot("var(--kiln-stopped)")}Kiln, stopped by 2025–26</div>
      <div>{dot("var(--kiln)", true)}800 m CPCB siting distance</div>
      <div>{dot("var(--school-near)")}School within 800 m of a kiln</div>
      <div className="mt-1 muted">Districts: % of children 5–14 within 800 m</div>
      <div className="flex gap-0.5">
        {["#fde9d9", "#f9c3a3", "#f08a62", "#d4532f", "#9c2a14"].map((c) => <span key={c} style={{ background: c, width: 30, height: 10 }} />)}
      </div>
      <div className="flex justify-between muted text-[11px]" style={{ width: 158 }}><span>0</span><span>2.6</span><span>5.5</span><span>9.7</span><span>16.3%</span></div>
    </div>
  );
}

export default function MapExplorer() {
  const { kilns, schools, districts, wayback, error } = useMapData();
  const params = useSearchParams();
  const [basemap, setBasemap] = useState<Basemap>("streets");
  const [layers, setLayers] = useState<Layers>({ districts: true, rings: true, kilns: true, schools: true, stopped: true });
  const lat = Number(params.get("lat")), lon = Number(params.get("lon"));
  const label = params.get("label") || "";
  const focus = useMemo(() => (lat && lon ? { lat, lon, zoom: Number(params.get("z")) || 16 } : null), [lat, lon, params]);
  const extra = useMemo(() => (focus ? [{ lat, lon, label: label || "Selected", color: "#7c3aed" }] : []), [focus, lat, lon, label]);
  useEffect(() => { if (focus) { setBasemap("satellite"); if (window.innerWidth < 900) setOpen(false); } }, [focus]);

  const [open, setOpen] = useState(true);
  const toggle = (k: keyof Layers) => setLayers((l) => ({ ...l, [k]: !l[k] }));
  return (
    <div style={{ position: "relative", height: "calc(100dvh - 49px)" }}>
      <MapView kilns={kilns} schools={schools} districts={districts} wayback={wayback}
               basemap={basemap} layers={layers} extra={extra} focus={focus} />
      {!open && <button className="btn" style={{ position: "absolute", top: 12, left: 12 }} onClick={() => setOpen(true)}>Layers & legend</button>}
      <aside className="panel" hidden={!open} style={{ position: "absolute", top: 12, left: 12, width: 290, maxWidth: "calc(100% - 24px)",
                                         maxHeight: "calc(100% - 60px)", overflow: "auto", padding: 14 }}>
        <div className="flex items-start justify-between gap-2">
          <div className="font-semibold">Kilns, schools and the 800 m rule</div>
          <button className="text-sm muted" aria-label="Hide panel" onClick={() => setOpen(false)}>✕</button>
        </div>
        <p className="text-[13px] muted mt-1">Click a kiln or school for details. {kilns.length ? `${kilns.length.toLocaleString("en-US")} kilns, ${schools.length} schools within 800 m.` : "Loading…"}</p>
        {error && <p className="text-[13px] mt-2" style={{ color: "var(--kiln)" }}>{error}</p>}
        <div className="mt-3 flex flex-col gap-1 text-sm">
          {([["kilns", "Kilns"], ["stopped", "Include stopped kilns"], ["rings", "800 m rings"], ["schools", "Schools near kilns"], ["districts", "District shading"]] as const).map(([k, l]) => (
            <label key={k} className="flex items-center gap-2"><input type="checkbox" checked={layers[k]} onChange={() => toggle(k)} />{l}</label>
          ))}
        </div>
        <div className="mt-3"><BasemapPicker value={basemap} onChange={setBasemap} wayback={wayback} /></div>
        <div className="mt-3"><Legend /></div>
      </aside>
    </div>
  );
}
