# Text for the "Emissions map A3" layout (step 26). Run inside QGIS:
#   exec(open("C:/Delhi Kiln/qgis/emissions_layout_text.py", encoding="utf-8").read())
from qgis.core import QgsProject, QgsLayoutItemLabel, QgsLayoutPoint, QgsLayoutSize

L = QgsProject.instance().layoutManager().layoutByName("Emissions map A3")
labs = sorted([i for i in L.items() if isinstance(i, QgsLayoutItemLabel)], key=lambda i: (i.pagePos().x(), i.pagePos().y()))
# left column: title (y=7), subtitle (y=18); right column by y: inset caption, key header, key body, method
title, sub = [i for i in labs if i.pagePos().x() < 100]
inset_cap, key_h, key_b, method = [i for i in labs if i.pagePos().x() > 100]

PM = "PM\u2082.\u2085"
title.setText("A third of brick-kiln smoke in the NCR is released within 800 m of a school")
sub.setText(f"Estimated {PM} emitted by brick kilns in one firing season, and the share from kilns within the CPCB 800 m "
            "siting distance of a school  \u00b7  National Capital Region, 2023\u201324")
inset_cap.setText(f"Inset: Matiyala, Ghaziabad \u2013 most kilns within 800 m of a school (blue box on main map)")
for sb in [i for i in L.items() if type(i).__name__ == "QgsLayoutItemScaleBar" and i.pagePos().y() < 200]:
    sb.attemptMove(QgsLayoutPoint(sb.pagePos().x(), 129.5 - sb.rect().height() - 1))
key_h.attemptMove(QgsLayoutPoint(275, 223.5))
key_b.attemptMove(QgsLayoutPoint(275, 229))
key_b.attemptResize(QgsLayoutSize(135, 33))
key_b.setText(
    f"\u2248 4,400\u201311,600 t {PM} per season from 3,057 kilns (low: zigzag, 4 M bricks/kiln; high: fixed chimney, 6 M)\n"
    "21% of it (940\u20132,460 t) comes from the 23% of kilns that have a school within 800 m\n"
    "Baghpat: 176 t from kilns near schools (low case), 2.5\u00d7 the next district\n"
    f"Most-affected schools (kilns within 800 m \u00b7 t {PM}, low case):\n"
    "  1  P.S. Matiyala, Ghaziabad \u2013 10 \u00b7 15 t        2  N.K. Memorial Public School, Dahapa, Hapur \u2013 8 \u00b7 14 t\n"
    "  3  U.P.S. Himmat Nagar, Hapur \u2013 7 \u00b7 11 t        4  P S Samaspur, Gautam Buddha Nagar \u2013 8 \u00b7 11 t\n"
    "Emissions at source, not air quality at the school (no dispersion model).")
method.setText(
    "Method: PM\u2082.\u2085 = bricks \u00d7 3 kg \u00d7 emission factor. Emission factors: World Bank (2020) Table 2.1 "
    "(zigzag 0.12, fixed chimney 0.21 g/kg fired brick). Bricks per kiln ASSUMED (4\u20136 million/season). "
    "Each kiln's share set by its 2023\u201324 Sentinel-2 firing frequency. Kilns: YOLO11 detector, firing-verified, "
    "non-kilns removed, every kiln checked by eye (doubtful ones by R. Sinha). Schools: UDISE (DataMeet), location-checked, shared points and points in fields removed.\n"
    "Data: Copernicus Sentinel-2 (ESA), SentinelKilnDB (IIT Gandhinagar, CC BY-NC 4.0), ESA WorldCover, UDISE/DataMeet, "
    "World Bank (CC BY 3.0 IGO), OpenStreetMap contributors, NCRPB boundaries (rebuilt).\n"
    "CRS: WGS 84 / UTM zone 43N (EPSG:32643)  \u00b7  Produced 13 October 2026  \u00b7  KilnWatch \u2013 Rashmi Sinha")
for i in (title, sub, inset_cap, key_h, key_b, method):
    i.refresh()
print("ok")
