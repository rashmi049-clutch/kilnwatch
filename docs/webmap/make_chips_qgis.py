r"""
Cut a 320 m x 320 m true-colour Sentinel-2 chip around every kiln, for the web
map popups ("what the AI saw"). Run with QGIS's Python (needs GDAL):
    "C:\Program Files\QGIS 3.40.6\bin\python-qgis-ltr.bat" docs\webmap\make_chips_qgis.py
Source: the 2023-24 median composites (data/s2/s2324, B4/B3/B2, reflectance x 10000),
mosaicked as a VRT so kilns on tile edges are not cut. One fixed stretch
(400-2600, gamma 0.8) for all chips so they are comparable.
Output: docs/webmap/chips.json  {det_index: base64 JPEG}
"""
import base64, csv, glob, io, json, os
import numpy as np
from osgeo import gdal
from PIL import Image

gdal.UseExceptions()
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, "docs", "webmap")
vrt = gdal.BuildVRT("/vsimem/s2324.vrt", sorted(glob.glob(os.path.join(ROOT, "data", "s2", "s2324", "*.tif"))))
x0, px, _, y0, _, py = vrt.GetGeoTransform()
N = 32  # pixels = 320 m
out = {}
with open(os.path.join(HERE, "chip_points.csv")) as f:
    for r in csv.DictReader(f):
        c = int((float(r["x"]) - x0) / px) - N // 2
        rw = int((float(r["y"]) - y0) / py) - N // 2
        c = max(0, min(c, vrt.RasterXSize - N)); rw = max(0, min(rw, vrt.RasterYSize - N))
        a = vrt.ReadAsArray(c, rw, N, N).astype("float32")           # (3, N, N)
        a = np.clip((a - 400) / 2200, 0, 1) ** 0.8
        img = Image.fromarray((a.transpose(1, 2, 0) * 255).astype("uint8"))
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=90)
        out[r["det_index"]] = base64.b64encode(buf.getvalue()).decode()
json.dump(out, open(os.path.join(HERE, "chips.json"), "w"))
sizes = [len(v) for v in out.values()]
print(len(out), "chips, mean", round(np.mean(sizes)), "chars, total", round(sum(sizes) / 1e6, 2), "MB")
