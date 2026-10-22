import Link from "next/link";
import districtsJson from "@/public/data/districts.json";
import schoolsJson from "@/public/data/schools_near.json";
import type { DistrictProps, School } from "@/lib/data";
import { fmt } from "@/lib/data";

export const metadata = { title: "Districts · KilnWatch" };

const districts = (districtsJson.features as { properties: DistrictProps }[]).map((f) => f.properties)
  .filter((d) => !d.excluded).sort((a, b) => (b.pct ?? 0) - (a.pct ?? 0));
const schools = schoolsJson as School[];

export default function DistrictsPage() {
  return (
    <main className="wrap flex flex-col gap-5">
      <div>
        <h1 className="h1">District cards</h1>
        <p className="lead">Children and schools inside the 800 m siting distance, by district, ranked by the share of children 5–14 exposed.
          Delhi is excluded: no firing kilns were found inside it.</p>
      </div>

      <div className="panel overflow-x-auto">
        <table className="tbl">
          <thead><tr><th>District</th><th>State</th><th className="num">Children 5–14 within 800 m</th><th className="num">Share</th>
            <th className="num">Kilns</th><th className="num">Kilns with a school ≤800 m</th><th className="num">Schools ≤800 m</th></tr></thead>
          <tbody>
            {districts.map((d) => (
              <tr key={d.name}>
                <td><a className="link" href={`#${encodeURIComponent(d.name)}`}>{d.name}</a></td>
                <td className="muted">{d.state}</td>
                <td className="num">{fmt(d.children_exposed)}</td>
                <td className="num"><b>{d.pct}%</b></td>
                <td className="num">{fmt(d.kilns)}</td>
                <td className="num">{fmt(d.kilns_with_school)}</td>
                <td className="num">{fmt(d.schools)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {districts.filter((d) => d.schools > 0).map((d) => {
          const top = schools.filter((s) => s.district === d.name).sort((a, b) => b.kilns_800m - a.kilns_800m || a.kiln_m - b.kiln_m).slice(0, 5);
          return (
            <section key={d.name} id={encodeURIComponent(d.name)} className="panel min-w-0 overflow-x-auto">
              <div className="flex items-baseline justify-between gap-2">
                <div className="h2" style={{ marginBottom: 0 }}>{d.name}</div>
                <span className="tag">{d.state}</span>
              </div>
              <p className="text-sm mt-1"><b>{d.pct}%</b> of children 5–14 ({fmt(d.children_exposed)} of {fmt(d.children_total)}) live within 800 m of a firing kiln.
                {" "}{fmt(d.kilns)} kilns, {fmt(d.schools)} schools inside the distance.</p>
              {top.length > 0 && (
                <table className="tbl mt-2">
                  <thead><tr><th>Schools with most kilns nearby</th><th className="num">Kilns ≤800 m</th><th className="num">Nearest</th></tr></thead>
                  <tbody>{top.map((s) => (
                    <tr key={s.id}>
                      <td><Link className="link" href={`/map/?lat=${s.lat}&lon=${s.lon}&z=15&label=${encodeURIComponent(s.name)}`}>{s.name}</Link>
                        <div className="text-[12px] muted">{s.village}</div></td>
                      <td className="num">{s.kilns_800m}</td>
                      <td className="num">{fmt(s.kiln_m)} m</td>
                    </tr>))}
                  </tbody>
                </table>
              )}
            </section>
          );
        })}
      </div>
      <p className="note">School points are official UDISE+ register locations, not field-verified. Children: WorldPop 2020 (100 m), counted once inside the union of all 800 m rings.</p>
    </main>
  );
}
