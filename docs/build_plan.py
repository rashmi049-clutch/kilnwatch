"""
Generate docs/plan.html (the living plan artifact) from the step list below.

To update the plan, edit a step's status / result here and re-run:
    python docs/build_plan.py
Status values: done, running, wait (needs Rashmi), next, todo, go.
"""

from datetime import date
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
HEAD = (HERE / "plan_style.css.html").read_text(encoding="utf-8")

ME, YOU, BOTH = "Claude", "You", "Together"

PHASES = [
    ("Phase 1 · Core", "Days 1–3", "Where are the kilns, and how many children study near them?", [
        (1, "Build the NCR boundary", ME, "done",
         "Put together the 25 NCR districts and check the area against the official figure.",
         "Every count is 'inside the NCR', so the boundary comes first. Indian boundary data is often wrong.",
         "OSM has Rajasthan's 2023 split; NCR uses the old Alwar and Bharatpur, so they were rebuilt.",
         "55,016 km² vs official 55,083 (−0.12%). Without the rebuild, ~3,200 km² of Rajasthan would be missing."),
        (2, "Check the boundary by eye", YOU, "done", "Look at the boundary in QGIS over OpenStreetMap.",
         "An area can match while the shape is wrong.", "", "Signed off."),
        (3, "Approve downloads", YOU, "done", "OK for packages and the kiln dataset.", "", "", "Installed; 3.7 GB dataset downloaded."),
        (4, "Get and check the kiln training data", ME, "done",
         "Download SentinelKilnDB, read the authors' code, convert boxes to map points.",
         "Our images must be made the same way as the training images.",
         "Row counts match; boxes sit exactly on kilns when drawn.",
         "4,114 unique NCR kilns (87% zig-zag). README and code disagree on dates. Tiles overlap heavily where state runs meet."),
        (5, "School locations", ME, "done",
         "Government SchoolGIS points, clipped to NCR, checked for misplacement.",
         "The headline counts children near kilns.",
         "Each school's own district compared with the district it sits in.",
         "43,904 schools. 10.5% sit 9–57 km from their own district, so they're excluded from the main count (shown separately)."),
        (6, "Check 30 schools on the basemap", YOU, "done",
         "For 30 random schools: is the dot on a building or on open land? Then the same check automated for all 43,904 schools.",
         "Measures location errors among the schools we keep.",
         "Spotting a school is hard at this resolution, so the question became building vs open land. The automated version uses the ESA WorldCover built-up map.",
         "You: 14 on buildings, 16 on open land. Automated: all 14 building dots confirmed; 10 of the 16 open-land dots are within 50 m of the village. 93% of schools are within 300 m of built-up land, 1% more than 800 m. Schools over 300 m away (6.4%) are flagged unreliable."),
        (7, "Fetch satellite images, both seasons", ME, "done",
         "630 tiles (10.24 km) per season: Nov 2023–Feb 2024 and Nov 2025–Feb 2026.",
         "The AI scans every part of the NCR in both seasons.",
         "Sentinel-2 median of clear scenes, same months both years, pixel-aligned grid.",
         "All 1,260 tiles (630 per season), no empty pixels anywhere. Overnight sleep paused it once; a keep-awake helper now prevents that."),
        (8, "Earth Engine sign-in", YOU, "done", "Approve access with your Google account.", "", "", "Connected to project geosync-448701."),
        (9, "Prepare a fair training set", ME, "done",
         "Train on a 150 km ring around the NCR; test only on NCR kilns.",
         "Testing on land the AI has seen inflates its score.",
         "0.5° spatial blocks, 2 km gap at the border, kiln-free tiles added.",
         "9,029 train / 2,657 val / 4,076 NCR test. Finding: 77% of the dataset's own test tiles overlap a training tile."),
        (10, "Train the kiln detector", ME, "done",
         "Fine-tune YOLO-OBB (tilted boxes) on the training tiles.",
         "The AI at the heart of every phase.",
         "Pretrained nano model, 256 px, flips and rotations only, up to 20 rounds on the processor.",
         "Stopped at the best round (13): validation mAP50 0.78. Later rounds did not improve. The laptop slept twice with the lid closed, which cost time."),
        (11, "Score the AI on the NCR, and measure domain shift", ME, "done",
         "Run on 4,076 NCR test tiles, once with the dataset's images and once with ours.",
         "Our images show green winter crops where the dataset's show bare fields. This measures what that costs.",
         "If the cost is large: retrain on our own images at the known kiln positions (kilns don't move).",
         "On dataset-style images F1 0.78; on ours 0.64. The fix (fine-tune on our-style chips) made it worse at every cut-off (best 0.54), because the labels don't match our images. Rejected and documented. Keeping the original model at confidence 0.25."),
        (12, "Verify detections", ME, "done",
         "Check whether detections are real kilns across the whole NCR, including areas the dataset never labelled.",
         "Measures false alarms on empty land, which step 11 can't.",
         "A visual check proved too hard at this resolution, so every detection was tested by whether it fires (the hot-spot signal from Phase 3), plus OpenStreetMap kiln tags.",
         "Estimated precision 0.71 from firing, matching 0.74 from the reference. 78% of OpenStreetMap kilns found. 3,447 firing-verified kilns at ~96% precision, used for the headline numbers."),
        (13, "Scan the whole NCR, both seasons", ME, "done",
         "Run the detector on all 630 tiles × 2 seasons and remove duplicates.",
         "The same model both years, so differences are real.",
         "Land-cover filter (kilns sit on bare ground, not cropland), cut-off chosen from the data.",
         "Raw 14,395 detections; after the filter 6,140 (2023-24) and 5,758 (2025-26). Kiln types (zig-zag vs FCBK) unreliable on our images, so not used."),
        (14, "Match kilns across seasons", ME, "done",
         "Label each kiln still firing, stopped, or new.",
         "Feeds H3 (do kilns near schools close faster?).",
         "Re-test firing at the same spot, so detector misses can't look like closures.",
         "Of 3,447 firing kilns, 2,983 still fire in 2025-26 and 464 (13.5%) don't; 71 new. 13.5% is an upper bound (about 10% after removing non-kilns). The planned miss-rate correction was rejected: it went negative because the re-tested kilns are strong firers."),
        (15, "Children within 800 m", ME, "done",
         "800 m zones around kilns: schools inside, plus children aged 5–14 living inside (WorldPop 2020).",
         "The headline number; tests H1 and H2.",
         "Two independent measures, since school-level pupil counts aren't openly available.",
         "About 605,000 children aged 5-14 and 1,708 schools within 800 m of a firing kiln (Delhi excluded); upper bound 1.28 M. Two-thirds in western UP. Rashmi spotted a 'kiln' on the IGI Airport apron: 157 non-kiln heat sources (airports, refinery, industrial estates, year-round heat) were then removed with two independent checks (OSM location + monsoon heat), cutting the headline by 9%. Rashmi then spotted two dots on one kiln on the web map: 25 duplicate detections (<70 m apart, cut-off read from the reference data) removed -> 3,265 kilns; exposure barely changed."),
        (16, "Cross-check one district in QGIS", BOTH, "done",
         "Repeat step 15 by hand in QGIS Processing for one district.", "Checks the code independently.", "20 minutes.",
         "Baghpat, done by Rashmi in QGIS without seeing the code's values: 415 kilns, 174 with a school within 800 m, 263 schools near a kiln - all three match the code exactly. Then a visual audit of 25 random kilns in Google Earth history (Rashmi): 21 active, 1 relict, 1 bare ground, 2 unclear -> measured precision 0.91 (95% CI 0.73-0.98), replacing the ~0.99 estimate. Found a new error type: relict kilns (old outline + faint false heat)."),
        (17, "Test H1–H3", ME, "done", "Confirm or reject each hypothesis with numbers.", "",
         "H3 uses a statistical test so a small difference isn't over-read.",
         "H1 confirmed (35% of kilns have a school within 800 m). H2 rejected as stated (top 3 districts hold 35%, not >50%; exposure is regional, western UP). H3 confirmed: kilns near schools stop 14.6% vs 13.3% elsewhere (95% CI -1.2 to +3.9 points, p = 0.31) - no sign that enforcement protects schools."),
    ]),
    ("Phase 2 · Did the policy work? (future work)", "—", "Did kilns switch to cleaner zig-zag designs, and how many are unregistered?", [
        (18, "Kiln maps for 2019, 2021, 2023, 2025", ME, "future",
         "Scan the NCR every other year with the same detector.",
         "Turns one snapshot into a trend.",
         "From 2019 only: earlier images are processed differently in India, a Landsat 9-style trap.", "Moved to future work (13 Oct 2026): needs 2-3 days of continuous laptop processing, not feasible on this machine; the project's main question is answered without it."),
        (19, "Zig-zag switch by district", ME, "future",
         "Share of zig-zag kilns per district, per year.",
         "Measures whether the order to convert actually happened, and where.", "", "Moved to future work: kiln type is unreliable on 10 m imagery (see report), so this needs a new method first."),
        (20, "Compare with state kiln registers", ME, "future",
         "Match detected kilns with state pollution board lists.",
         "Kilns seen from space but missing from registers = possibly unregistered.",
         "Registers may list village names only; matching by village where needed.", "Moved to future work: no usable public register was located yet (not verified that none exists); matching would also need village-level geocoding."),
    ]),
    ("Phase 3 · Caught in the act", "Day 5", "Are kilns firing when they're ordered shut?", [
        (21, "Can firing be seen? Go/no-go test", ME, "done",
         "Hot-spot index (NHI) at 100 kilns vs 100 random spots, every clear image of 2024.",
         "If firing can't be seen, Phase 3 stops here.",
         "Also tested whether the hot spot moves around the kiln (fire) or stays put (material).",
         "GO. Kilns flag in 33% of dry-season images vs 4% for random spots, and drop to 2% in the monsoon. Hot spot wanders ~26 m, up to 84 m."),
        (22, "Monthly firing record for every kiln", ME, "done",
         "Hot-spot frequency per kiln per month, 2023–2026.",
         "Firing is judged by how often a kiln flags, not by one hit.", "",
         "Season measured: kilns relight Oct-Nov, peak Feb-May (up to 66% of clear images), near background in Aug-Sep monsoon. Dry-season firing net of background fell 0.50 -> 0.42 -> 0.37 over 2023-26. Checked for the Sentinel-2C switch (Jan 2025): control background flat, so not a false-heat artefact; sensitivity to real fire can't be tested this way (partially checked)."),
        (23, "Do kilns keep firing in pollution emergencies?", ME, "done",
         "Compare kiln firing on GRAP Stage III/IV days with other days, Dec 2024 onwards.",
         "The official schedules exempt kilns from Stage III/IV closures (stone crushers and mines shut). This tests whether that exemption matters.",
         "Net of control points, because smog on ban days nudges the index up slightly.",
         "Both official schedules read: kilns are NOT closed at Stage III or IV. First run (per kiln): 37% hot on emergency days vs 45% otherwise - but month-by-month results swung from -45 to +32 points: kilns photographed on the same day share that day's conditions, so the real sample is ~109 days, not 3,290 kilns. That CI was withdrawn. Redone with days as the unit (23 usable days, 10 emergency): kilns clearly fire on emergency days (+42 pts over background), but the within-month effect is -5.5 pts, 95% CI -21.6 to +10.0, p = 0.62 - inconclusive. Sentinel-2 sees too few clear emergency days to measure a response."),
        (24, "Emissions estimate", ME, "done",
         "Bricks per kiln × 3 kg × published emission factors (World Bank 2020 Table 2.1), split between kilns by firing frequency.",
         "Turns 'kilns nearby' into tonnes of pollution.", "Cross-checked against Weyant et al. (2014) South Asian totals (0.73 g/brick → 9,500–14,300 t, inside our range). Station comparison not possible: emissions ≠ concentrations without a dispersion model.",
         "2023–24, NCR excl. Delhi: 4,700–12,300 t PM2.5 (low = zigzag, 4 M bricks/kiln; high = fixed chimney, 6 M). 31.9% from kilns within 800 m of a school (34.6% of kilns). Baghpat highest (730–1,900 t). Worst school: JHS Rampur Kheri, Shamli - 12 kilns within 800 m. Bricks per kiln is ASSUMED; kiln type unknown."),
    ]),
    ("Phase 4 · Product", "Days 6–7", "Something an interviewer can click through.", [
        (25, "Interactive web map", ME, "done",
         "Search a school or village; see nearby kilns, type, firing record, children exposed.",
         "A finished tool, not just a report.", "Static web map, free hosting.",
         "Published: https://claude.ai/artifact/RG48cSJJLW8tCXFSJkQ98m - districts shaded by share of children exposed; click any of 3,265 kilns for its 2023-24 firing, 2025-26 status, schools within 800 m and audit verdict; 800 m zones and 36,738 schools appear when zoomed in; search by school, village or district. Vector-only (the artifact host blocks map tiles); a satellite basemap can be added for GitHub Pages. Sentinel-2 kiln pictures were tried and removed (10 m = blurry); each kiln now links to a sharp satellite view."),
        (26, "Finished maps", BOTH, "done",
         "QGIS print layouts: exposure by district; emissions near schools.",
         "Every map: scale bar, north arrow, legend, CRS, credits, date.", "Checked every map element on the export; found and fixed a broken north-arrow path on map 1.",
         "Map 1 (A3): share of children within 800 m by district - Baghpat 32.8%, NCR 7.3%. Map 2 (A3): PM2.5 from kilns within 800 m of a school by district (Baghpat 300 t, low case), 15 most-affected schools, inset on Rampur Kheri (12 kilns within 800 m). Change and firing are shown as charts in the report rather than extra maps."),
        (27, "Finish the report", ME, "done",
         "The LaTeX report, updated after every step; executive summary; tidy-up.", "",
         "Boundary reference areas verified (NCRPB 55,083 km², Census 2011 Alwar 8,380, Bharatpur 5,066). Summary numbers re-read from the output tables (caught a wrong school count: 36,738, not 39,000).",
         "Executive summary with 6 findings and 3 recommendations; title page marked complete; data-sources table brought up to date (WorldPop, WorldCover, OSM, Google Earth, GRAP added; statuses fixed); stale 'pending' markers removed; processing-parameters appendix completed."),
        (28, "README for GitHub", ME, "done", "Opens with the headline number and main map.",
         "Interviewers spend about 30 seconds on it.", "Every number re-read from outputs/tables or the report (H2 top-3 share computed: 37%).",
         "README: headline, map, findings table, hypotheses, recommendations, pipeline diagram, trust checks, rejected methods, reproduce steps, licences. Added requirements.txt (pinned) and .gitignore (raw data, logs, and commercial basemap screenshots excluded). Web-size map PNGs made for the README. At step 29 the web-map link becomes the GitHub Pages URL."),
        (29, "Read through and publish", YOU, "done", "Read the README and report, push to your GitHub; host the web map on GitHub Pages.",
         "Your project, your sign-off.", "Checked live: repo shows 3 commits signed with the hidden GitHub email; Pages returns 200 for both the short address and /webmap/. Optional later: free Esri developer key for a sharp satellite basemap.",
         "Published 14 Oct 2026: github.com/rashmi049-clutch/kilnwatch (MIT code, CC BY-NC data). Live map: rashmi049-clutch.github.io/kilnwatch/webmap/. Topics and website set in About."),
    ]),
]

WHO = {ME: "w-me", YOU: "w-you", BOTH: "w-both"}
ST = {"done": ("done", "st done", "isdone"), "go": ("done · GO", "st done", "isdone"),
      "running": ("running", "st wait", "iswait"), "wait": ("waiting on you", "st wait", "iswait"),
      "next": ("next", "st", ""), "todo": ("—", "st", ""),
      "future": ("future work", "st", "")}


def step_html(n, title, who, status, what, why, how, result):
    label, stcls, dcls = ST[status]
    rows = "".join(f"<dt>{k}</dt><dd>{escape(v)}</dd>" for k, v in (("What", what), ("Why", why), ("How", how)) if v)
    res = f'<div class="result"><b>Result:</b> {escape(result)}</div>' if result else ""
    op = " open" if status == "wait" else ""
    return (f'<details class="{dcls}"{op}><summary><span class="num">{n}</span>'
            f'<span class="title">{escape(title)} <span class="who {WHO[who]}">{who}</span></span>'
            f'<span class="right"><span class="{stcls}">{label}</span><span class="chev">›</span></span></summary>'
            f'<div class="body"><dl>{rows}</dl>{res}</div></details>')


def main() -> None:
    steps = [s for _, _, _, ss in PHASES for s in ss]
    total = sum(s[3] != "future" for s in steps)   # steps moved to future work are out of scope
    done = sum(s[3] in ("done", "go") for s in steps)
    active = sum(s[3] in ("running", "wait") for s in steps)
    body = []
    for name, days, q, ss in PHASES:
        d = sum(s[3] in ("done", "go") for s in ss)
        n = sum(s[3] != "future" for s in ss)
        tag = f"{d}/{n} done" if n else "moved to future work"
        body.append(f'<h2>{escape(name)} <span class="sub">{days} · steps {ss[0][0]}–{ss[-1][0]} · {tag}</span></h2>'
                    f'<p style="color:var(--muted)">{escape(q)}</p><div class="steps">'
                    + "".join(step_html(*s) for s in ss) + "</div>")
    waiting = [f"step {s[0]} ({s[1].lower()})" for s in steps if s[3] == "wait"]
    html = f"""{HEAD}
<div class="wrap">
  <div class="eyebrow">GeoAI project · living plan</div>
  <h1>NCR Kiln Watch</h1>
  <div class="meta"><span>Rashmi Sinha</span><span>Updated {date.today():%d %b %Y}</span><span>NCR, 55,016 km²</span><span>EPSG:32643</span><span>{total} steps · 4 phases · 7 days</span><span>Folder: C:\\Delhi Kiln</span></div>
  <div class="goal">
    <div class="eyebrow">What KilnWatch answers</div>
    <p><b>Where is every brick kiln around Delhi, does it follow the rules, is it firing when it's banned, and how many children study or live within 800 m?</b></p>
    <p style="color:var(--muted);font-size:14.5px">H1: at least 25% of kilns have a school within 800 m. H2: the top 3 districts hold over half the exposed children. H3: kilns near schools close no faster than kilns elsewhere.</p>
  </div>
  <div class="progress">
    <div class="eyebrow">Progress</div>
    <div class="bar" role="img" aria-label="{done} of {total} steps done">
      <span style="width:{100 * done / total:.1f}%;background:var(--done)"></span><span style="width:{100 * active / total:.1f}%;background:var(--accent)"></span>
    </div>
    <div class="counts"><span><b>{done}</b>done</span><span><b>{active}</b>running or waiting on you</span><span><b>{total - done - active}</b>to go</span><span><b>{total}</b>total</span></div>
  </div>
  <div class="legend">
    <span class="who w-me">Claude</span> does it and reports back
    <span class="who w-you">You</span> needs your eyes, account or decision
    <span class="who w-both">Together</span>
    <span style="color:var(--muted)">· Click any step to open its box</span>
  </div>
  {''.join(body)}
  <div class="note"><b>Waiting on you:</b> {', '.join(waiting) if waiting else 'nothing right now'}.</div>
  <footer>Living plan, generated by docs/build_plan.py. Data: SentinelKilnDB (IIT Gandhinagar, CC BY-NC 4.0), Copernicus Sentinel-2, WorldPop, UDISE+ / SchoolGIS, © OpenStreetMap contributors.</footer>
</div>
"""
    (HERE / "plan.html").write_text(html, encoding="utf-8")
    print(f"plan.html: {done}/{total} done, {active} active")


if __name__ == "__main__":
    main()
