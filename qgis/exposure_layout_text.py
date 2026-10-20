# Key-number and method text for the "Exposure map A3" layout. Run inside QGIS:
#   exec(open("C:/Delhi Kiln/qgis/exposure_layout_text.py", encoding="utf-8").read())
from qgis.core import QgsProject, QgsLayoutItemLabel

L = QgsProject.instance().layoutManager().layoutByName("Exposure map A3")
for i in [x for x in L.items() if isinstance(x, QgsLayoutItemLabel)]:
    t = i.text()
    if t.startswith("\u2248"):
        i.setText("\u2248 528,000 children aged 5\u201314 (6.4%) live within 800 m of a firing kiln\n"
                  "837 schools stand within 800 m  \u00b7  23% of 3,057 kilns have a school within 800 m\n"
                  "Kilns near schools were no more likely to stop firing by 2025\u201326 (10.2% vs 10.7%)")
    elif t.startswith("Method:"):
        i.setText(t.replace("non-kiln heat sources removed. Precision 0.91 by visual audit of 25 random kilns (95% CI 0.73\u20130.98).",
                            "non-kiln heat sources removed; every kiln near a school checked by eye on Esri imagery (101 removed).")
                   .replace("(101 removed).", "every kiln checked by eye, doubtful ones by R. Sinha (208 non-kilns removed).")
                   .replace("Schools: UDISE (DataMeet), location-checked.", "Schools: UDISE (DataMeet), location-checked, shared points and points in fields removed."))
    i.refresh()
print("ok")
