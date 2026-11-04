"use client";
// "Why this matters": the story behind the numbers, in a slide-over panel on top of the map.
// Facts here are either from this project's own outputs (summary.json) or cited inline.
import Link from "next/link";
import type { DistrictProps, School, Summary } from "@/lib/data";
import { fmt, fmtRound } from "@/lib/data";

function H({ n, children }: { n: number; children: React.ReactNode }) {
  return <h3 style={{ margin: "18px 0 6px", fontSize: 16, fontWeight: 700, display: "flex", gap: 8, alignItems: "baseline" }}>
    <span className="mono" style={{ fontSize: 12, color: "var(--kiln)" }}>{n}</span>{children}</h3>;
}
const P = ({ children }: { children: React.ReactNode }) => <p style={{ margin: "0 0 8px", fontSize: 14, lineHeight: 1.5 }}>{children}</p>;
const Src = ({ children }: { children: React.ReactNode }) => <p style={{ margin: "4px 0 0", fontSize: 11, color: "var(--muted)" }}>{children}</p>;

// 24-hour strip: the kiln fire never stops; the school day sits inside it
function DayStrip() {
  const pct = (h: number) => `${(h / 24) * 100}%`;
  return (
    <div style={{ margin: "6px 0 10px" }}>
      <div style={{ position: "relative", height: 18, background: "var(--kiln)", borderRadius: 4 }}>
        <span style={{ position: "absolute", left: 6, top: 1, fontSize: 11, color: "#fff", fontWeight: 600 }}>kiln fire: day and night</span>
      </div>
      <div style={{ position: "relative", height: 18, marginTop: 3 }}>
        <span style={{ position: "absolute", left: pct(8), width: pct(6), height: 18, background: "var(--school)", borderRadius: 4 }} />
        <span style={{ position: "absolute", left: pct(14.3), top: 1, fontSize: 11, color: "var(--muted)" }}>school day (typical 8 am–2 pm)</span>
      </div>
      <div className="mono" style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--muted)", marginTop: 2 }}>
        <span>0:00</span><span>6:00</span><span>12:00</span><span>18:00</span><span>24:00</span>
      </div>
    </div>
  );
}

// 12-month strip: firing season vs monsoon shutdown
function YearStrip() {
  const m = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
  const fire = [1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1];
  return (
    <div style={{ margin: "6px 0 10px" }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(12, 1fr)", gap: 2 }}>
        {m.map((x, i) => <div key={i} style={{ textAlign: "center" }}>
          <div style={{ height: 14, borderRadius: 3, background: fire[i] ? "var(--kiln)" : "#DDE1DC" }} />
          <div className="mono" style={{ fontSize: 10, color: "var(--muted)" }}>{x}</div>
        </div>)}
      </div>
      <div style={{ fontSize: 11, color: "var(--muted)" }}>Red: firing season (relit Oct–Nov, peak Feb–May). Grey: monsoon shutdown.</div>
    </div>
  );
}

export default function Guide({ summary, dRank, topSchools, onDistrict, onSchool, onClose }: {
  summary: Summary; dRank: DistrictProps[]; topSchools: School[];
  onDistrict: (name: string) => void; onSchool: (s: School) => void; onClose: () => void;
}) {
  const [lo, hi] = summary.emissions;
  return (
    <div role="dialog" aria-modal="true" aria-label="Why this matters" onClick={onClose}
         style={{ position: "fixed", inset: 0, zIndex: 50, background: "rgba(20,24,28,.35)", display: "flex", justifyContent: "flex-end" }}>
      <div onClick={(e) => e.stopPropagation()}
           style={{ width: "min(560px, 100%)", height: "100%", overflowY: "auto", background: "#fff", padding: "18px 22px 28px", boxShadow: "-8px 0 30px rgba(0,0,0,.2)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>Why this matters</h2>
          <button onClick={onClose} aria-label="Close" style={{ fontSize: 22, lineHeight: 1, padding: "4px 8px" }}>×</button>
        </div>
        <P><span style={{ color: "var(--muted)" }}>Brick kilns burn coal and waste all season long, often right next to villages and schools. This page explains what they release, who breathes it, and how to find the worst places on the map.</span></P>

        <H n={1}>What the kilns release</H>
        <P>Burning coal, wood and agricultural waste gives off:</P>
        <ul style={{ margin: "0 0 8px 18px", fontSize: 14, lineHeight: 1.6, listStyle: "disc" }}>
          <li><b>PM<sub>2.5</sub></b>: fine dust small enough to reach deep into the lungs and the blood.</li>
          <li><b>Black carbon</b>: soot, the dark part of PM<sub>2.5</sub>.</li>
          <li><b>Sulphur dioxide (SO<sub>2</sub>)</b> from the sulphur in coal, and <b>carbon monoxide (CO)</b> from incomplete burning.</li>
        </ul>
        <div style={{ background: "#FBEDE6", borderRadius: 10, padding: 12, fontSize: 14, color: "#5E3020" }}>
          NCR kilns release an estimated <b>{fmtRound(lo.pm25_t, 100)}–{fmtRound(hi.pm25_t, 100)} tonnes of PM<sub>2.5</sub></b> and {fmtRound(lo.bc_t, 100)}–{fmtRound(hi.bc_t, 100)} t of black carbon per season (this project, World Bank 2020 emission factors).
        </div>

        <H n={2}>Why children are affected more</H>
        <ul style={{ margin: "0 0 8px 18px", fontSize: 14, lineHeight: 1.6, listStyle: "disc" }}>
          <li>They <b>breathe faster</b> and take in more air for their body weight than adults.</li>
          <li>Their <b>lungs and immune systems are still growing</b>, so damage now can last for life.</li>
          <li>They spend <b>more time outdoors</b>, playing and walking to school.</li>
        </ul>
        <P>Health studies link fine-particle pollution in childhood to respiratory infections, asthma and slower lung growth.</P>
        <P><b>What this project measures:</b> how many children <i>live and study near</i> kilns. It does not measure illness.</P>
        <Src>WHO (2018) <i>Air pollution and child health: prescribing clean air</i>; UNICEF (2016) <i>Clear the Air for Children</i>.</Src>

        <H n={3}>Do kilns run during school hours?</H>
        <P><b>Yes, always.</b> The common NCR kilns (fixed-chimney and zigzag) are <i>continuous</i> kilns. The fire travels slowly round an oval track of stacked bricks and is kept burning <b>day and night</b> for the whole season. There is no “off” time in the school day.</P>
        <DayStrip />
        <YearStrip />
        <P>The firing season covers most of the school year. Only the summer vacation (roughly mid-May to June in north India) gives children a break, and even then they live nearby.</P>
        <Src>CSE (2017) <i>Overview of brick manufacturing technologies</i>; firing months measured from Sentinel-2 heat detections in this project.</Src>

        <H n={4}>Why school children?</H>
        <ul style={{ margin: "0 0 8px 18px", fontSize: 14, lineHeight: 1.6, listStyle: "disc" }}>
          <li><b>The law names schools.</b> CPCB siting rules (2022) say a kiln must be at least <b>800 m</b> from schools, hospitals and habitation. That gives a clear yardstick to check.</li>
          <li><b>Schools are mapped.</b> Every school has a register location (UDISE+), so each one can be checked.</li>
          <li><b>Children are there for hours</b>, every school day, while the kilns fire.</li>
        </ul>
        <P>The headline <b>{fmtRound(summary.children_800m)} children</b> (aged 5–14) is counted from where children <i>live</i> (WorldPop 2020 population grid), so it includes children who do not go to school.</P>

        <H n={5}>Why kilns, and how we found them</H>
        <P><b>Why kilns:</b> they are a big, local source of smoke that can be seen from space and counted. They have a legal distance rule, so the result points to action: which kilns to inspect.</P>
        <P><b>How we found them:</b> Sentinel-2 satellite images (10 m pixels) of the whole NCR, with a shortwave-infrared <b>heat test</b> that keeps only kilns that were actually firing in 2023–24. Every kiln was then checked by eye on high-resolution imagery. An analyst audit of a random sample found {summary.audit.active} of {summary.audit.random_kilns - summary.audit.unclear} working. <Link className="link" href="/method/">Full method</Link></P>
        <P>Result: <b>{fmt(summary.kilns)} firing kilns</b>, and <b>{summary.pct_kilns_with_school}%</b> of them have a school within 800 m.</P>

        <H n={6}>Find the most affected areas</H>
        <P><b>One click:</b> close this panel and <b>click any spot on the map</b>. The right panel counts the kilns and schools within 800 m of that point, and gives that district’s share of children exposed.</P>
        <div style={{ fontSize: 13, fontWeight: 600, margin: "8px 0 4px" }}>Worst districts (% of children within 800 m)</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {dRank.slice(0, 5).map((d) => <button key={d.name} className="btn" onClick={() => onDistrict(d.name)}>{d.name} · <span className="mono">{d.pct}%</span></button>)}
        </div>
        <div style={{ fontSize: 13, fontWeight: 600, margin: "12px 0 4px" }}>Schools with the most kilns within 800 m</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {topSchools.slice(0, 5).map((s) => <button key={s.id} onClick={() => onSchool(s)} className="text-left"
              style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 13, padding: "6px 8px", borderRadius: 8, background: "var(--soft)" }}>
            <span>{s.name}, <span style={{ color: "var(--muted)" }}>{s.village}, {s.district}</span></span>
            <span className="mono" style={{ color: "var(--kiln)", whiteSpace: "nowrap" }}>{s.kilns_800m} kilns</span>
          </button>)}
        </div>
      </div>
    </div>
  );
}
