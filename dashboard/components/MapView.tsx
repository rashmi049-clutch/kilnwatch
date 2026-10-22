"use client";
// The one map used across the dashboard. MapLibre GL with our own layers on a free basemap
// (CARTO streets, Esri World Imagery, or a dated Esri Wayback release).
import { useEffect, useRef } from "react";
import maplibregl, { type GeoJSONSource, type Map as MLMap, type MapMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { DistrictProps, KilnRow, School, Wayback } from "@/lib/data";
import { STATUS_LABEL, fmt } from "@/lib/data";
import { circle, googleSat, waybackLink } from "@/lib/geo";

export type Basemap = "streets" | "satellite" | string; // a Wayback date selects that release
export type Layers = { districts: boolean; rings: boolean; kilns: boolean; schools: boolean; stopped: boolean };
export type Extra = { lat: number; lon: number; label: string; color?: string }[];
export type Pick = { lat: number; lon: number; kiln?: KilnRow; school?: School };

type Props = {
  kilns: KilnRow[];
  schools: School[];
  districts: GeoJSON.FeatureCollection | null;
  wayback: Wayback[];
  basemap: Basemap;
  layers: Layers;
  extra?: Extra;                 // e.g. analyst edits, highlighted search result
  focus?: { lat: number; lon: number; zoom?: number } | null;
  onPick?: (p: Pick) => void;    // edit mode: click returns location + feature under the cursor
  popups?: boolean;
};

// keyless Esri basemaps (CARTO raster tiles now require an API key)
const GRAY = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}";
const GRAY_REF = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}";
const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const css = (v: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || "#888";

function kilnFC(kilns: KilnRow[]): GeoJSON.FeatureCollection {
  return { type: "FeatureCollection", features: kilns.map((k, i) => ({
    type: "Feature", id: i, geometry: { type: "Point", coordinates: [k[2], k[1]] },
    properties: { i, st: k[4], n: k[5] } })) };
}
function ringFC(kilns: KilnRow[]): GeoJSON.FeatureCollection {
  return { type: "FeatureCollection", features: kilns.map((k) => ({
    type: "Feature", geometry: { type: "Polygon", coordinates: [circle(k[1], k[2], 800)] }, properties: { st: k[4] } })) };
}
function schoolFC(schools: School[]): GeoJSON.FeatureCollection {
  return { type: "FeatureCollection", features: schools.map((s, i) => ({
    type: "Feature", geometry: { type: "Point", coordinates: [s.lon, s.lat] }, properties: { i, near: s.kiln_m <= 800 ? 1 : 0 } })) };
}
function extraFC(extra: Extra = []): GeoJSON.FeatureCollection {
  return { type: "FeatureCollection", features: extra.map((e) => ({
    type: "Feature", geometry: { type: "Point", coordinates: [e.lon, e.lat] }, properties: { label: e.label, color: e.color || "#7c3aed" } })) };
}

function kilnPopup(k: KilnRow) {
  const [id, lat, lon, hot, st, n, near, d] = k;
  return `<b>Brick kiln #${id}</b>${d ? ` · ${d}` : ""}<br>
    Fired in ${hot}% of clear 2023–24 dry-season scenes<br>
    2025–26: <b>${STATUS_LABEL[String(st)]}</b><br>
    Schools within 800 m: <b>${n}</b>${n ? "" : ` (nearest ${fmt(near)} m)`}<br>
    <a href="${googleSat(lat, lon)}" target="_blank" rel="noopener">Google satellite</a> ·
    <a href="${waybackLink(lat, lon)}" target="_blank" rel="noopener">Esri Wayback</a>`;
}
function schoolPopup(s: School) {
  return `<b>${s.name}</b><br>${s.village}, ${s.district}<br>${s.cat} · ${s.mgmt}<br>
    Kilns within 800 m: <b>${s.kilns_800m}</b> · nearest kiln ${fmt(s.kiln_m)} m<br>
    <span style="color:var(--muted)">Official UDISE+ register location, not field-verified.</span><br>
    <a href="${googleSat(s.lat, s.lon)}" target="_blank" rel="noopener">Google satellite</a> ·
    <a href="https://www.google.com/maps/search/${encodeURIComponent(s.name + ", " + s.village)}/@${s.lat},${s.lon},16z" target="_blank" rel="noopener">Search name</a>`;
}

export default function MapView(p: Props) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const ready = useRef(false);
  const latest = useRef(p);
  latest.current = p;

  // create once
  useEffect(() => {
    if (!box.current) return;
    const m = new maplibregl.Map({
      container: box.current,
      style: { version: 8, sources: {
          streets: { type: "raster", tiles: [GRAY], tileSize: 256, maxzoom: 16, attribution: "Basemap © Esri, HERE, Garmin, © OpenStreetMap contributors" },
          "streets-ref": { type: "raster", tiles: [GRAY_REF], tileSize: 256, maxzoom: 16 },
          satellite: { type: "raster", tiles: [ESRI], tileSize: 256, maxzoom: 19,
                       attribution: "Imagery © Esri, Maxar, Earthstar Geographics" } },
        layers: [{ id: "streets", type: "raster", source: "streets" },
                 { id: "streets-ref", type: "raster", source: "streets-ref" },
                 { id: "satellite", type: "raster", source: "satellite", layout: { visibility: "none" } }] },
      center: [77.25, 28.75], zoom: 7.6, attributionControl: { compact: true },
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    map.current = m;
    if (process.env.NODE_ENV === "development") (window as unknown as { __kwmap: MLMap }).__kwmap = m; // debugging only

    m.on("load", () => {
      const q = latest.current;
      m.addSource("districts", { type: "geojson", data: q.districts || { type: "FeatureCollection", features: [] } });
      m.addLayer({ id: "districts-fill", type: "fill", source: "districts", paint: {
        "fill-color": ["case", ["==", ["get", "excluded"], true], "rgba(0,0,0,0)",
          ["step", ["to-number", ["get", "pct"], 0],"#fde9d9", 2.6, "#f9c3a3", 5.5, "#f08a62", 9.7, "#d4532f", 16.3, "#9c2a14"]],
        "fill-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0.45, 11, 0.2, 13, 0] } });
      m.addLayer({ id: "districts-line", type: "line", source: "districts", paint: { "line-color": "#6c665f", "line-width": 0.8 } });
      m.addSource("rings", { type: "geojson", data: ringFC(q.kilns) });
      m.addLayer({ id: "rings", type: "fill", source: "rings", paint: { "fill-color": css("--kiln"), "fill-opacity": 0.1 } });
      m.addLayer({ id: "rings-line", type: "line", source: "rings", paint: { "line-color": css("--kiln"), "line-width": 0.6, "line-opacity": 0.5 } });
      m.addSource("schools", { type: "geojson", data: schoolFC(q.schools) });
      m.addLayer({ id: "schools", type: "circle", source: "schools", paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 2.5, 12, 5, 16, 8],
        "circle-color": ["case", ["==", ["get", "near"], 1], css("--school-near"), css("--school")],
        "circle-stroke-color": "#fff", "circle-stroke-width": 1 } });
      m.addSource("kilns", { type: "geojson", data: kilnFC(q.kilns) });
      m.addLayer({ id: "kilns", type: "circle", source: "kilns", paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 2.5, 12, 5.5, 16, 9],
        "circle-color": ["case", ["==", ["get", "st"], 0], css("--kiln-stopped"), css("--kiln")],
        "circle-stroke-color": "#1a1a1a", "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 7, 0.3, 12, 1] } });
      m.addSource("extra", { type: "geojson", data: extraFC(q.extra) });
      m.addLayer({ id: "extra", type: "circle", source: "extra", paint: {
        "circle-radius": 8, "circle-color": ["get", "color"], "circle-opacity": 0.85, "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
      ready.current = true;
      applyAll();
    });

    const pick = (e: MapMouseEvent) => {
      const q = latest.current;
      const hit = m.queryRenderedFeatures(e.point, { layers: ["extra", "kilns", "schools"].filter((l) => m.getLayer(l)) });
      const f = hit[0];
      if (f?.layer.id === "extra" && !q.onPick) {
        const [lon, lat] = (f.geometry as GeoJSON.Point).coordinates;
        new maplibregl.Popup({ offset: 8 }).setLngLat([lon, lat]).setText(String(f.properties.label)).addTo(m);
        return;
      }
      const kiln = f?.layer.id === "kilns" ? q.kilns[f.properties.i as number] : undefined;
      const school = f?.layer.id === "schools" ? q.schools[f.properties.i as number] : undefined;
      if (q.onPick) { q.onPick({ lat: +e.lngLat.lat.toFixed(6), lon: +e.lngLat.lng.toFixed(6), kiln, school }); return; }
      if (q.popups === false) return;
      if (kiln) new maplibregl.Popup({ offset: 8 }).setLngLat([kiln[2], kiln[1]]).setHTML(kilnPopup(kiln)).addTo(m);
      else if (school) new maplibregl.Popup({ offset: 8 }).setLngLat([school.lon, school.lat]).setHTML(schoolPopup(school)).addTo(m);
    };
    m.on("click", pick);
    for (const l of ["kilns", "schools"]) {
      m.on("mouseenter", l, () => (m.getCanvas().style.cursor = "pointer"));
      m.on("mouseleave", l, () => (m.getCanvas().style.cursor = latest.current.onPick ? "crosshair" : ""));
    }
    return () => { m.remove(); map.current = null; ready.current = false; };
  }, []);

  function applyAll() {
    const m = map.current; if (!m || !ready.current) return;
    const q = latest.current;
    // basemap
    const isWay = q.basemap !== "streets" && q.basemap !== "satellite";
    m.setLayoutProperty("streets", "visibility", q.basemap === "streets" ? "visible" : "none");
    m.setLayoutProperty("streets-ref", "visibility", q.basemap === "streets" ? "visible" : "none");
    m.setLayoutProperty("satellite", "visibility", q.basemap === "satellite" ? "visible" : "none");
    for (const w of q.wayback) {
      const id = "wb-" + w.date;
      if (isWay && w.date === q.basemap && !m.getSource(id)) {
        m.addSource(id, { type: "raster", tiles: [w.url], tileSize: 256, maxzoom: 19, attribution: `Esri World Imagery Wayback ${w.date}` });
        m.addLayer({ id, type: "raster", source: id }, "districts-fill");
      }
      if (m.getLayer(id)) m.setLayoutProperty(id, "visibility", isWay && w.date === q.basemap ? "visible" : "none");
    }
    // layers
    const vis = (on: boolean) => (on ? "visible" : "none");
    m.setLayoutProperty("districts-fill", "visibility", vis(q.layers.districts));
    m.setLayoutProperty("rings", "visibility", vis(q.layers.rings));
    m.setLayoutProperty("rings-line", "visibility", vis(q.layers.rings));
    m.setLayoutProperty("kilns", "visibility", vis(q.layers.kilns));
    m.setLayoutProperty("schools", "visibility", vis(q.layers.schools));
    const flt = q.layers.stopped ? null : ["!=", ["get", "st"], 0];
    m.setFilter("kilns", flt as maplibregl.FilterSpecification | null);
    m.setFilter("rings", flt as maplibregl.FilterSpecification | null);
    m.setFilter("rings-line", flt as maplibregl.FilterSpecification | null);
    m.getCanvas().style.cursor = q.onPick ? "crosshair" : "";
  }

  useEffect(applyAll, [p.basemap, p.layers, p.onPick, p.wayback]);
  useEffect(() => {
    const m = map.current; if (!m || !ready.current) return;
    (m.getSource("kilns") as GeoJSONSource).setData(kilnFC(p.kilns));
    (m.getSource("rings") as GeoJSONSource).setData(ringFC(p.kilns));
  }, [p.kilns]);
  useEffect(() => {
    const m = map.current; if (!m || !ready.current) return;
    (m.getSource("schools") as GeoJSONSource).setData(schoolFC(p.schools));
  }, [p.schools]);
  useEffect(() => {
    const m = map.current; if (!m || !ready.current || !p.districts) return;
    (m.getSource("districts") as GeoJSONSource).setData(p.districts);
  }, [p.districts]);
  useEffect(() => {
    const m = map.current; if (!m || !ready.current) return;
    (m.getSource("extra") as GeoJSONSource).setData(extraFC(p.extra));
  }, [p.extra]);
  useEffect(() => {
    const m = map.current; if (!m || !p.focus) return;
    const go = () => m.flyTo({ center: [p.focus!.lon, p.focus!.lat], zoom: p.focus!.zoom ?? 16, speed: 1.6 });
    if (ready.current) go(); else m.once("load", go);
  }, [p.focus]);

  return <div ref={box} style={{ position: "absolute", inset: 0 }} />;
}

export function districtFC(d: GeoJSON.FeatureCollection | null) {
  return d as (GeoJSON.FeatureCollection<GeoJSON.Geometry, DistrictProps> | null);
}
