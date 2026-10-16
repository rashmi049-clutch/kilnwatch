"""
Contact sheets of the current Esri World Imagery around points, 25 per sheet (300 m
windows, red circle on the point), for checking by eye what is there. Viewing only:
sheets stay in a scratch folder and are never published.

    python analysis/render_sheets.py points.json out_prefix [start stop]
    points.json: [[det_index, lat, lon, ...], ...]
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wayback_check as wb  # noqa: E402

W, COLS, PER = 360, 5, 25
src, prefix = sys.argv[1], sys.argv[2]
start = int(sys.argv[3]) if len(sys.argv) > 3 else 0      # first point (multiple of 25)
stop = int(sys.argv[4]) if len(sys.argv) > 4 else None
allpts = json.load(open(src))
pts = allpts[start:stop]
latest = sorted(wb.CFG.values(), key=lambda v: v["itemTitle"])[-1]

with ThreadPoolExecutor(8) as ex:
    imgs = list(ex.map(lambda p: wb.window(latest, p[1], p[2])[0], pts))
font = ImageFont.load_default()
for s in range(0, len(pts), PER):
    part = list(zip(pts[s:s + PER], imgs[s:s + PER]))
    rows = (len(part) + COLS - 1) // COLS
    sheet = Image.new("RGB", (W * COLS, (W + 22) * rows), "white")
    d = ImageDraw.Draw(sheet)
    for n, (p, img) in enumerate(part):
        x, y = (n % COLS) * W, (n // COLS) * (W + 22)
        if img is not None:
            sheet.paste(img.resize((W, W)), (x, y + 22))
        d.ellipse((x + W / 2 - 14, y + 22 + W / 2 - 14, x + W / 2 + 14, y + 22 + W / 2 + 14), outline="red", width=2)
        d.text((x + 5, y + 5), f"{start + s + n + 1}. id {p[0]}", fill="black", font=font)
    sheet.save(f"{prefix}_{(start + s) // PER + 1:02d}.png")
print("sheets:", (len(pts) + PER - 1) // PER)
