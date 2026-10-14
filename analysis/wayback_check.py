"""
Visual-check helper: show one kiln point on several dates of Esri World Imagery
(World Imagery Wayback), so a site hidden by haze or cloud on the current basemap
can be judged from another capture.

For each point, every ~6th Wayback release is sampled; releases that serve
identical imagery at the point are dropped (same tile bytes), and up to MAX_DATES
distinct captures are kept, each labelled with its capture date from the release's
metadata layer (SRC_DATE2).

Viewing only - Esri imagery is not redistributed; sheets stay in the scratchpad.

    python analysis/wayback_check.py points.json out_prefix
    points.json: [[det_index, lat, lon, ...], ...]
"""
import hashlib
import io
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
Z, HALF_M, PX, MAX_DATES, PER_SHEET = 17, 150, 300, 5, 6
S = requests.Session()
S.headers["User-Agent"] = "KilnWatch visual check"
CFG = S.get("https://s3-us-west-2.amazonaws.com/config.maptiles.arcgis.com/waybackconfig.json", timeout=60).json()
REL = sorted(CFG.values(), key=lambda v: v["itemTitle"])[::-6][:24]      # newest first, ~every 6th release


def tile_xy(lat, lon):
    n = 2 ** Z
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def get(url):
    for _ in range(3):
        try:
            r = S.get(url, timeout=30)
            if r.status_code == 200:
                return r.content
        except requests.RequestException:
            pass
    return None


def window(rel, lat, lon):
    """300 m window around the point from a 2x2 block of z17 tiles; returns (image, centre-tile hash)."""
    x, y = tile_xy(lat, lon)
    mpp = 156543.03 * math.cos(math.radians(lat)) / 2 ** Z           # metres per pixel
    half = HALF_M / mpp
    px, py = x * 256, y * 256
    x0, y0 = int((px - half) // 256), int((py - half) // 256)
    x1, y1 = int((px + half) // 256), int((py + half) // 256)
    canvas = Image.new("RGB", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
    centre = None
    for tx in range(x0, x1 + 1):
        for ty in range(y0, y1 + 1):
            b = get(rel["itemURL"].format(level=Z, row=ty, col=tx))
            if b is None:
                return None, None
            if tx == int(x) and ty == int(y):
                centre = hashlib.md5(b).hexdigest()
            canvas.paste(Image.open(io.BytesIO(b)).convert("RGB"), ((tx - x0) * 256, (ty - y0) * 256))
    cx, cy = px - x0 * 256, py - y0 * 256
    crop = canvas.crop((int(cx - half), int(cy - half), int(cx + half), int(cy + half))).resize((PX, PX))
    return crop, centre


def capture_date(rel, lat, lon):
    for layer in (5, 6, 4):
        try:
            j = S.get(f"{rel['metadataLayerUrl']}/{layer}/query", timeout=30, params={
                "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects", "outFields": "SRC_DATE2", "returnGeometry": "false", "f": "json"}).json()
            f = j.get("features")
            if f:
                v = f[0]["attributes"]["SRC_DATE2"]
                return __import__("datetime").datetime.utcfromtimestamp(v / 1000).strftime("%Y-%m-%d") if isinstance(v, (int, float)) else str(v)
        except Exception:
            pass
    return rel["itemTitle"][-11:-1] + " (release)"


def dates_for(pt):
    i, lat, lon = pt[0], pt[1], pt[2]
    seen, out = set(), []
    for rel in REL:
        img, h = window(rel, lat, lon)
        if img is None or h in seen:
            continue
        seen.add(h)
        date = capture_date(rel, lat, lon)
        if date in {t for t, _ in out}:          # same capture, reprocessed tiles
            continue
        out.append((date, img))
        if len(out) == MAX_DATES:
            break
    return i, sorted(out, key=lambda t: t[0])


def main(src, prefix):
    pts = json.load(open(src))
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(dates_for, pts))
    font = ImageFont.load_default()
    for s in range(0, len(res), PER_SHEET):
        part = res[s:s + PER_SHEET]
        sheet = Image.new("RGB", (PX * MAX_DATES + 110, (PX + 18) * len(part)), "white")
        d = ImageDraw.Draw(sheet)
        for r, (i, dates) in enumerate(part):
            y = r * (PX + 18)
            d.text((4, y + PX // 2), f"id {i}", fill="black", font=font)
            for c, (date, img) in enumerate(dates):
                x = 110 + c * PX
                sheet.paste(img, (x, y + 16))
                d.ellipse((x + PX / 2 - 12, y + 16 + PX / 2 - 12, x + PX / 2 + 12, y + 16 + PX / 2 + 12), outline="red", width=2)
                d.text((x + 4, y + 2), date, fill="black", font=font)
        out = f"{prefix}_{s // PER_SHEET + 1:02d}.png"
        sheet.save(out)
        print("saved", out, [(i, [t for t, _ in ds]) for i, ds in part])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
