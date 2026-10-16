# Full eye check of all remaining kilns - IN PROGRESS (paused 15 Oct 2026)

Requested by Rashmi Sinha: check every kiln by its structure (ring, chimney, brick rows,
burnt ground), not by the heat test alone. Nothing has been removed from the data yet.

- points_all_1913.json        all 1,913 kilns not previously checked by eye [det_index, lat, lon]
- first_pass_verdicts.csv     current Esri imagery, by Claude: 47 not_kiln, 135 unclear;
                              every point NOT listed = kiln structure clearly visible (1,731)
- points_unclear_135.json     the unclear ones, to be re-checked on older dates

Next session:
1. python analysis/wayback_check.py outputs/tables/pending_full_eye_check/points_unclear_135.json <scratch>/wbar
   and judge each unclear point on up to 5 Esri dates (rule: kiln visible around the 2023-24 season).
2. Re-confirm the 47 not_kiln verdicts on older dates too before removal.
3. Append final verdicts to outputs/tables/visual_check_near_schools.csv with group
   "remaining kilns, full eye check", then run apply_visual_check.py -> exposure.py ->
   exposure_excl_delhi.py -> map_exposure_data.py -> h3_stop_near_schools.py -> emissions.py ->
   build_webmap.py -> QGIS text scripts + export -> update report/README -> commit; user pushes.
