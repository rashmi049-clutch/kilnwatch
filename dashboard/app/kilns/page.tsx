import kilnsJson from "@/public/data/kilns.json";
import schoolsJson from "@/public/data/schools_near.json";
import type { KilnRow, School } from "@/lib/data";
import { distM } from "@/lib/geo";
import KilnTable, { type KilnNear } from "@/components/KilnTable";

export const metadata = { title: "Kilns near schools · KilnWatch" };

// computed at build time: every kiln with at least one school inside 800 m, and which schools
const kilns = kilnsJson as KilnRow[];
const schools = schoolsJson as School[];
const rows: KilnNear[] = kilns.filter((k) => k[5] > 0).map((k) => {
  const near = schools.map((s) => ({ s, d: distM(k[1], k[2], s.lat, s.lon) })).filter((x) => x.d <= 800).sort((a, b) => a.d - b.d);
  return { id: k[0], lat: k[1], lon: k[2], district: k[7], firing: k[3], status: k[4], n: near.length,
           nearest_m: Math.round(near[0]?.d ?? k[6]), schools: near.map((x) => `${x.s.name} (${Math.round(x.d)} m)`) };
});

export default function KilnsPage() {
  return (
    <main className="wrap flex flex-col gap-4">
      <div>
        <h1 className="h1">Kilns with a school inside 800 m</h1>
        <p className="lead">The Central Pollution Control Board&apos;s siting criteria keep brick kilns at least 800 m from schools and settlements.
          This list gives every kiln that fired in 2023–24 with a registered school inside that distance, for inspection and follow-up.</p>
      </div>
      <KilnTable rows={rows} />
      <p className="note">Kilns: firing confirmed by a shortwave-infrared heat test on Sentinel-2 and checked by eye on high-resolution imagery.
        Distances use official school register locations (not field-verified), so treat values within ~100 m of the limit as borderline.
        The siting rule applies to kiln locations as approved; older kilns may predate it.</p>
    </main>
  );
}
