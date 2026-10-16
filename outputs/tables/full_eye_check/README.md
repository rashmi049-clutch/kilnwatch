# Full eye check of all remaining kilns - COMPLETE (16 Oct 2026)

Every kiln not checked earlier (1,913) was judged by its structure on current Esri imagery
by Claude; the 182 doubtful ones were decided independently by Rashmi Sinha on an
annotation page (shuffled, Claude's verdicts hidden).

- points_all_1913.json        the 1,913 kilns [det_index, lat, lon]
- first_pass_verdicts.csv     Claude's first pass: 47 not_kiln, 135 unclear (others = kiln)
- rashmi_verdicts_182.csv     Rashmi Sinha's verdicts: 138 active, 43 not_kiln, 1 unclear
- review_removals_166.json    the 166 earlier removals offered for review (16 reviewed, 2 restored)

All verdicts are merged into ../visual_check_near_schools.csv and applied by
analysis/apply_visual_check.py. The 150 unreviewed removals are covered by
analysis/exposure_sensitivity_removals.py (range reported in the report).
