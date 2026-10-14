# Key-number and method text for the "Exposure map A3" layout. Run inside QGIS:
#   exec(open("C:/Delhi Kiln/qgis/exposure_layout_text.py", encoding="utf-8").read())
from qgis.core import QgsProject, QgsLayoutItemLabel

L = QgsProject.instance().layoutManager().layoutByName("Exposure map A3")
for i in [x for x in L.items() if isinstance(x, QgsLayoutItemLabel)]:
    t = i.text()
    if t.startswith("\u2248"):
        i.setText("\u2248 539,000 children aged 5\u201314 (6.5%) live within 800 m of a firing kiln\n"
                  "1,191 schools stand within 800 m  \u00b7  32% of 3,096 kilns have a school within 800 m\n"
                  "Kilns near schools were no more likely to stop firing by 2025\u201326 (10.8% vs 10.9%)")
    elif t.startswith("Method:"):
        i.setText(t.replace("non-kiln heat sources removed. Precision 0.91 by visual audit of 25 random kilns (95% CI 0.73\u20130.98).",
                            "non-kiln heat sources removed; every kiln near a school checked by eye on Esri imagery (101 removed).")
                   .replace("(101 removed).", "and every weak-firing kiln found with Earth Engine (166 non-kilns removed).")
                   .replace("Schools: UDISE (DataMeet), location-checked.", "Schools: UDISE (DataMeet), location-checked, shared points removed."))
    i.refresh()
print("ok")
