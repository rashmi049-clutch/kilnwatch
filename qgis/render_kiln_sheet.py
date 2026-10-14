# Contact sheet of Esri World Imagery tiles around kiln points, for visual checks (viewing only,
# not for publication). Run inside QGIS:
#   SRC, OUT, START, N = "<points.json>", "<sheet.png>", 0, 25
#   exec(open("C:/Delhi Kiln/qgis/render_kiln_sheet.py", encoding="utf-8").read())
# points.json: [[det_index, lat, lon, schools_within_800m], ...]
import json
from qgis.core import (QgsProject, QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsPointXY,
                       QgsMapSettings, QgsRectangle, QgsMapRendererParallelJob)
from qgis.PyQt.QtCore import QSize, QPointF
from qgis.PyQt.QtGui import QImage, QPainter, QColor, QFont, QPen

P = QgsProject.instance()
esri = P.mapLayersByName("Esri World Imagery")[0]
pts = json.load(open(SRC))[START:START + N]
t3 = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"), QgsCoordinateReferenceSystem("EPSG:3857"), P)
W, COLS, HALF = 360, 5, 150 * 1.14          # 300 m across; 1.14 = Web Mercator stretch near 29 N
rows = (len(pts) + COLS - 1) // COLS
sheet = QImage(W * COLS, (W + 22) * rows, QImage.Format_RGB32)
sheet.fill(QColor("white"))
pa = QPainter(sheet)
pa.setFont(QFont("Arial", 12, QFont.Bold))
for n, (i, lat, lon, ns) in enumerate(pts):
    m = t3.transform(QgsPointXY(lon, lat))
    ms = QgsMapSettings()
    ms.setLayers([esri])
    ms.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
    ms.setExtent(QgsRectangle(m.x() - HALF, m.y() - HALF, m.x() + HALF, m.y() + HALF))
    ms.setOutputSize(QSize(W, W))
    job = QgsMapRendererParallelJob(ms)
    job.start()
    job.waitForFinished()
    x, y = (n % COLS) * W, (n // COLS) * (W + 22)
    pa.drawImage(x, y + 22, job.renderedImage())
    pa.setPen(QPen(QColor("red"), 2))
    pa.drawEllipse(QPointF(x + W / 2, y + 22 + W / 2), 14, 14)
    pa.setPen(QColor("black"))
    pa.drawText(x + 5, y + 16, f"{START + n + 1}. id {i}  ({ns} sch)")
pa.end()
sheet.save(OUT)
print("saved", OUT, len(pts))
