import Link from "next/link";
import summaryJson from "@/public/data/summary.json";
import districtsJson from "@/public/data/districts.json";
import type { DistrictProps, Summary } from "@/lib/data";
import { fmt, fmtRound } from "@/lib/data";

const summary = summaryJson as unknown as Summary;
const districts = (districtsJson.features as { properties: DistrictProps }[]).map((f) => f.properties)
  .filter((d) => !d.excluded && d.pct !== null).sort((a, b) => (b.pct ?? 0) - (a.pct ?? 0));

const STAKEHOLDERS = [
  { who: "Parents and school heads", q: "How close is the nearest working kiln to my school?", href: "/schools/", cta: "Find a school" },
  { who: "District administration", q: "Which districts and villages carry the most exposure?", href: "/districts/", cta: "District cards" },
  { who: "Pollution control boards", q: "Which kilns have a school inside the 800 m siting distance?", href: "/kilns/", cta: "Kilns near schools" },
  { who: "Researchers and reviewers", q: "How was this measured, and how accurate is it?", href: "/method/", cta: "Method & accuracy" },
];

export default function Overview() {
  const max = districts[0]?.pct ?? 1;
  const [far, near] = [summary.stop_rates.find((r) => r.near_school.startsWith("no")), summary.stop_rates.find((r) => !r.near_school.startsWith("no"))];
  const restored = summary.children_range.find((r) => String(r.layer).startsWith("unreviewed"));
  return (
    <main className="wrap flex flex-col gap-6">
      <section>
        <h1 className="h1">Brick kilns and schoolchildren in Delhi-NCR</h1>
        <p className="lead">
          India&apos;s pollution board sets 800 m as the minimum distance between a brick kiln and schools or homes.
          Using satellite imagery we mapped every firing kiln in the NCR outside Delhi and counted the children and schools inside that distance.
        </p>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          [`≈${fmtRound(summary.children_800m)}`, "children aged 5–14 live within 800 m of a firing kiln",
            restored ? `range ${fmtRound(summary.children_800m)}–${fmtRound(Number(restored.children))}` : ""],
          [fmt(summary.schools_800m), "registered schools within 800 m of a kiln", "official UDISE+ locations"],
          [fmt(summary.kilns), "kilns firing in 2023–24", "every one checked by eye"],
          [`${summary.pct_kilns_with_school}%`, "of kilns have a school within 800 m", ""],
        ].map(([n, l, s]) => (
          <div key={l} className="panel">
            <div className="kpi-num">{n}</div>
            <div className="kpi-label">{l}</div>
            {s && <div className="text-[12px] muted mt-2">{s}</div>}
          </div>
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <div className="panel">
          <div className="h2">Share of children 5–14 living within 800 m, by district</div>
          <div className="flex flex-col gap-1.5">
            {districts.slice(0, 12).map((d) => (
              <div key={d.name} className="grid grid-cols-[130px_1fr_52px] items-center gap-2 text-sm">
                <span className="truncate">{d.name}</span>
                <span style={{ background: "var(--line)", borderRadius: 3, height: 12 }}>
                  <span style={{ display: "block", height: 12, borderRadius: 3, width: `${(100 * (d.pct ?? 0)) / max}%`, background: "var(--kiln)" }} />
                </span>
                <span className="text-right tabular-nums">{d.pct}%</span>
              </div>
            ))}
          </div>
          <p className="text-[12px] muted mt-3">Top 12 of {districts.length} districts. WorldPop 2020 children inside the union of 800 m rings. <Link className="link" href="/districts/">All districts</Link></p>
        </div>
        <div className="panel flex flex-col gap-3">
          <div className="h2">Are kilns near schools being shut down?</div>
          {far && near && (
            <div className="flex flex-col gap-2 text-sm">
              {[near, far].map((r) => (
                <div key={r.near_school} className="grid grid-cols-[1fr_auto] gap-2">
                  <span>{r.near_school === "school within 800 m" ? "Kilns with a school within 800 m" : "Kilns with no school nearby"}</span>
                  <b className="tabular-nums">{r.stop_rate_pct}% stopped</b>
                  <span className="col-span-2" style={{ background: "var(--line)", height: 10, borderRadius: 3 }}>
                    <span style={{ display: "block", height: 10, borderRadius: 3, width: `${r.stop_rate_pct * 5}%`, background: "var(--kiln-stopped)" }} />
                  </span>
                </div>
              ))}
            </div>
          )}
          <p className="text-sm">
            No. Kilns near schools stopped firing by 2025–26 no more often than others
            (difference {summary.stop_test.diff_pp} points, 95% CI {summary.stop_test.ci[0]} to {summary.stop_test.ci[1]}).
          </p>
          <p className="note">An earlier, apparent effect came from parks and stadiums misread as kilns. It disappeared once every kiln was checked by eye.</p>
        </div>
      </section>

      <section>
        <div className="h2">Questions this dashboard answers</div>
        <div className="grid gap-3 sm:grid-cols-2">
          {STAKEHOLDERS.map((s) => (
            <Link key={s.href} href={s.href} className="panel block hover:border-[var(--accent)]">
              <div className="text-[12px] muted">{s.who}</div>
              <div className="mt-1 font-medium">{s.q}</div>
              <div className="mt-2 text-sm" style={{ color: "var(--accent)" }}>{s.cta} →</div>
            </Link>
          ))}
        </div>
      </section>

      <footer className="text-[12px] muted">
        Data built {summary.built}. {summary.study_area}. Kilns: Sentinel-2 (ESA Copernicus). Schools: UDISE+ register. Children: WorldPop 2020.
        Analysis and audits: Rashmi Sinha.
      </footer>
    </main>
  );
}
