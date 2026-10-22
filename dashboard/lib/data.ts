// Types and loaders for the JSON written by analysis/export_dashboard_data.py.

// [id, lat, lon, firing %, status 2025-26 (1 firing, 0 stopped, -1 unknown), schools 800 m, nearest school m, district, check]
export type KilnRow = [number, number, number, number, 1 | 0 | -1, number, number, string, string];

export type School = {
  id: string; lat: number; lon: number; name: string; village: string; district: string; state: string;
  cat: string; mgmt: string; rural: boolean; kiln_m: number; kilns_800m: number;
};

export type SchoolsCompact = {
  cols: string[];
  lut: Record<"district" | "state" | "cat" | "mgmt", string[]>;
  rows: (string | number)[][];
};

export type DistrictProps = {
  name: string; state: string; excluded: boolean; pct: number | null; children_exposed: number;
  children_total: number; kilns: number; kilns_with_school: number; schools: number; area_km2: number;
};

export type Summary = {
  built: string; study_area: string; kilns: number; schools_800m: number; children_800m: number;
  pct_kilns_with_school: number;
  upper_all_filtered: { kilns: number; schools: number; children: number };
  children_range: Record<string, string | number>[];
  stop_rates: { near_school: string; kilns: number; stopped: number; stop_rate_pct: number }[];
  stop_test: { diff_pp: number; ci: [number, number]; p: number };
  emissions: { case: string; pm25_t: number; bc_t: number }[];
  audit: { random_kilns: number; active: number; unclear: number; by: string };
  sources: { layer: string; source: string; licence: string }[];
};

export type Wayback = { year: string; date: string; url: string };

export const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
export const dataUrl = (name: string) => `${BASE}/data/${name}`;

export async function loadJSON<T>(name: string): Promise<T> {
  const r = await fetch(dataUrl(name));
  if (!r.ok) throw new Error(`Could not load ${name} (${r.status})`);
  return r.json() as Promise<T>;
}

export function expandSchools(c: SchoolsCompact): School[] {
  const i = Object.fromEntries(c.cols.map((k, n) => [k, n])) as Record<string, number>;
  return c.rows.map((r) => ({
    id: r[i.id] as string, lat: r[i.lat] as number, lon: r[i.lon] as number, name: r[i.name] as string,
    village: r[i.village] as string, district: c.lut.district[r[i.district] as number],
    state: c.lut.state[r[i.state] as number], cat: c.lut.cat[r[i.cat] as number], mgmt: c.lut.mgmt[r[i.mgmt] as number],
    rural: r[i.rural] === 1, kiln_m: r[i.kiln_m] as number, kilns_800m: r[i.kilns_800m] as number,
  }));
}

export const STATUS_LABEL: Record<string, string> = { "1": "still firing", "0": "stopped", "-1": "not determined" };

export const fmt = (n: number) => n.toLocaleString("en-US");
export const fmtRound = (n: number, to = 1000) => (Math.round(n / to) * to).toLocaleString("en-US");
