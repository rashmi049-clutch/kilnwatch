import summaryJson from "@/public/data/summary.json";
import type { Summary } from "@/lib/data";
import { fmt, fmtRound } from "@/lib/data";

export const metadata = { title: "Method & accuracy · KilnWatch" };
const summary = summaryJson as unknown as Summary;
const REPO = "https://github.com/rashmi049-clutch/kilnwatch";

const STEPS = [
  ["Detect", "A YOLO11 oriented-box detector, fine-tuned on a public kiln dataset, run over Sentinel-2 imagery (10 m) of the whole NCR, 2023–24 season."],
  ["Confirm firing", "A shortwave-infrared heat test on every clear dry-season Sentinel-2 scene keeps only sites that were actually hot (firing) in 2023–24."],
  ["Check by eye", "Every remaining kiln was checked on high-resolution Esri imagery; doubtful ones were judged by the analyst in Google Earth history. Parks, stadiums and truck yards that passed as kilns were removed."],
  ["Count exposure", "800 m rings (CPCB siting distance) around each kiln; children 5–14 from WorldPop 2020 counted once inside the union of rings; schools from the UDISE+ register."],
  ["Test closures", "Each kiln's 2025–26 status from the same heat test, compared between kilns with and without a school within 800 m."],
];

export default function MethodPage() {
  const low = summary.emissions[0], high = summary.emissions[summary.emissions.length - 1];
  return (
    <main className="wrap flex flex-col gap-5">
      <div>
        <h1 className="h1">Method and accuracy</h1>
        <p className="lead">How the numbers were produced, how they were checked, and what they cannot tell you.
          Full report, code and processing parameters: <a className="link" href={REPO}>GitHub</a>.</p>
      </div>

      <section className="panel">
        <div className="h2">Pipeline</div>
        <ol className="flex flex-col gap-2 text-sm">
          {STEPS.map(([t, d], i) => (
            <li key={t} className="grid grid-cols-[28px_1fr] gap-2">
              <span className="tabular-nums muted">{i + 1}.</span><span><b>{t}.</b> {d}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="grid gap-3 md:grid-cols-2">
        <div className="panel">
          <div className="h2">Accuracy checks</div>
          <table className="tbl">
            <tbody>
              <tr><td>Random audit of kilns in Google Earth history (analyst: {summary.audit.by})</td>
                <td className="num"><b>{summary.audit.active}/{summary.audit.random_kilns - summary.audit.unclear}</b> working{summary.audit.unclear ? `, ${summary.audit.unclear} unclear` : ""}</td></tr>
              <tr><td>Kilns checked by eye</td><td className="num"><b>all {fmt(summary.kilns)}</b></td></tr>
              {summary.completeness && (
                <tr><td>Firing kilns in an independent hand-labelled inventory (SentinelKilnDB) that the map found</td>
                  <td className="num"><b>{Math.round(100 * summary.completeness.recall)}%</b> of {fmt(summary.completeness.ref_firing)}</td></tr>
              )}
              <tr><td>Closures near vs away from schools (difference)</td>
                <td className="num">{summary.stop_test.diff_pp} pts (95% CI {summary.stop_test.ci[0]} to {summary.stop_test.ci[1]})</td></tr>
            </tbody>
          </table>
        </div>
        <div className="panel">
          <div className="h2">Ranges, not single numbers</div>
          <table className="tbl">
            <thead><tr><th>Scenario</th><th className="num">Kilns</th><th className="num">Schools</th><th className="num">Children</th></tr></thead>
            <tbody>
              {summary.children_range.map((r) => (
                <tr key={String(r.layer)}><td>{String(r.layer)}</td><td className="num">{fmt(Number(r.kilns))}</td>
                  <td className="num">{fmt(Number(r.schools))}</td><td className="num">{fmtRound(Number(r.children))}</td></tr>
              ))}
              {summary.completeness && (<>
                <tr><td>corrected for kilns the map missed</td>
                  <td className="num">{fmt(summary.completeness.kilns[0])}–{fmt(summary.completeness.kilns[1])}</td><td className="num">–</td>
                  <td className="num">{fmtRound(summary.completeness.children[0])}–{fmtRound(summary.completeness.children[1])}</td></tr>
                <tr><td>ceiling: every inventory kiln, firing or not</td>
                  <td className="num">{fmt(summary.completeness.outer.kilns)}</td><td className="num">{fmt(summary.completeness.outer.schools)}</td>
                  <td className="num">{fmtRound(summary.completeness.outer.children)}</td></tr>
              </>)}
            </tbody>
          </table>
          <p className="text-[12px] muted mt-2">“Unreviewed removals restored” puts back every site removed without an analyst decision: the upper bound if those removals were wrong.</p>
          {summary.completeness && (
            <p className="text-[12px] muted mt-2">“Corrected for kilns the map missed” compares the map with SentinelKilnDB, a hand-labelled kiln inventory, after giving both the same heat test.
              The {fmt(summary.completeness.missed_added)} firing inventory kilns the map missed were added and exposure recounted; capture–recapture estimates the rest.
              Missed kilns sit mostly where kilns are already mapped, so children rise much less than kilns. The two lists are not fully independent, so even this range is probably low.
              The ceiling assumes every kiln that failed the heat test was really firing, which is unlikely.</p>
          )}
        </div>
      </section>

      <section className="panel">
        <div className="h2">School locations</div>
        <p className="text-sm">School points come from the official UDISE+ register (Ministry of Education / NIC SchoolGIS). They are not field-verified.
          Before counting, points were dropped if they fell in the wrong district, more than 300 m from built-up land, more than 50 m from any building,
          or stacked on schools of other villages, plus points the analyst reported as wrong. An ongoing analyst check compares register points
          with named map listings; results will be added here.</p>
      </section>

      <section className="panel">
        <div className="h2">Emissions (estimate)</div>
        <p className="text-sm">Season PM<sub>2.5</sub> from all {fmt(summary.kilns)} kilns: about {fmt(low.pm25_t)} t ({low.case}) to {fmt(high.pm25_t)} t ({high.case}).
          Emission factors from published kiln measurements; production per kiln is assumed, not measured.</p>
      </section>

      <section className="panel">
        <div className="h2">Limitations</div>
        <ul className="list-disc pl-5 text-sm flex flex-col gap-1">
          <li>School register locations can be tens to hundreds of metres off; some real schools near kilns are missing from the register, so school counts are a minimum.</li>
          <li>WorldPop is a modelled population surface (2020), not a census count.</li>
          <li>800 m is a siting distance, not a health threshold; living inside it does not measure dose.</li>
          <li>The map misses about one firing kiln in five, so the headline counts are minimums (corrected range above).</li>
          <li>Firing status comes from heat detected in clear Sentinel-2 scenes; small or intermittent firing can be missed.</li>
        </ul>
      </section>

      <section className="panel">
        <div className="h2">Data sources</div>
        <table className="tbl">
          <thead><tr><th>Layer</th><th>Source</th><th>Licence</th></tr></thead>
          <tbody>{summary.sources.map((s) => <tr key={s.layer}><td>{s.layer}</td><td>{s.source}</td><td>{s.licence}</td></tr>)}</tbody>
        </table>
        <p className="text-[12px] muted mt-2">Coordinates WGS 84 (EPSG:4326) for display; all distances and areas computed in UTM 43N (EPSG:32643). Data built {summary.built}.</p>
      </section>
    </main>
  );
}
