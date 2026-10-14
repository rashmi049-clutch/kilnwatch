# Legend for the "Emissions map A3" layout (step 26). Run inside QGIS:
#   exec(open("C:/Delhi Kiln/qgis/emissions_layout_legend.py", encoding="utf-8").read())
# Layers in the "Emissions map" group get fixed names (suffix "[em]") identified by
# source, so they never clash with the exposure map's layers; legend text is set as
# a legend-only label, which does not rename the layer.
from qgis.core import (QgsProject, QgsLayoutItemLegend, QgsLayoutPoint, QgsSingleSymbolRenderer,
                       QgsMapLayerLegendUtils)

P = QgsProject.instance()
L = P.layoutManager().layoutByName("Emissions map A3")
G = P.layerTreeRoot().findGroup("Emissions map")


def key(l):
    s = l.source()
    if "ncr_32643" in s: return "ncr"
    if "ncr_districts" in s: return "dbound"
    if "district_emissions" in s: return "choro"
    if "district_exposure" in s: return "delhi" if "excluded" in s else "names"
    if "schools_top15_800m" in s: return "ring"
    if "schools_top15" in s: return "top_inset" if l.labelsEnabled() else "top"
    if "schools_map" in s: return "schools"
    if "kilns_emissions" in s:
        return "kiln_near" if '"near_school" = 1' in s else "kiln_other" if '"near_school" = 0' in s else "kiln_inset"


lay = {}
for n in G.findLayers():
    k = key(n.layer())
    lay[k] = n.layer()
    n.layer().setName(f"{k} [em]")

PM = "PM\u2082.\u2085"
leg = [i for i in L.items() if isinstance(i, QgsLayoutItemLegend)][0]
leg.setAutoUpdateModel(False)
root = leg.model().rootGroup()
root.removeAllChildren()


def put(group, k, label):
    n = group.addLayer(lay[k])
    n.setCustomProperty("legend/title-label", label)
    if isinstance(lay[k].renderer(), QgsSingleSymbolRenderer):   # one symbol: label sits on the symbol row
        QgsMapLayerLegendUtils.setLegendNodeUserLabel(n, 0, label)
    leg.model().refreshLayerLegend(n)


m = root.addGroup("Main map")
put(m, "choro", f"{PM} from kilns within 800 m~of a school (t per season, low case)")
put(m, "delhi", "Delhi NCT \u2013 excluded (kilns not permitted)")
put(m, "kiln_near", f"Kiln with a school within 800 m~(size = {PM})")
put(m, "kiln_other", "Other kiln")
put(m, "top", f"15 schools with the most kiln~{PM} within 800 m")
put(m, "ncr", "NCR boundary")
i = root.addGroup("Inset")
put(i, "kiln_inset", f"Kiln (size = {PM}, 0.4\u20133.1 t)")
put(i, "ring", "800 m around a top-15 school")
put(i, "schools", "Schools")
put(i, "dbound", "District boundary")
leg.setTitle("Legend")
leg.setWrapString("~")
leg.adjustBoxSize()
leg.refresh()
leg.attemptMove(QgsLayoutPoint(12, 276 - leg.rect().height()))
print("legend ok", leg.rect().height(), sorted(lay))
