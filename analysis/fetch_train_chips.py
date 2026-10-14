"""
Fix for domain shift - training chips in this study's own imagery style.

Step 11 showed the detector loses F1 0.78 -> 0.64 when moved from the
dataset's single-scene imagery to our seasonal median. Kilns do not move,
so the dataset's labels still apply at the same ground position: for every
ring train/val patch, fetch a 128 x 128 px chip of our 2023-24 median
composite centred on the patch centre, in the same UTM 43N 10 m grid.

The per-patch labels are re-used unchanged. Small offsets between the
authors' native grid and ours (<= 1-2 px, larger in the UTM 44N part of the
ring) are tolerated by the fine-tune and do not touch the NCR test, which is
scored by ground-position matching.

NCR patches are NOT fetched: the NCR stays a pure test area.

Output:
    data/kilns/yolo_ours/{train,val}/{images,labels}/   same stems as yolo/
Resumable.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import ee
import numpy as np
import requests
from PIL import Image
from pyproj import Transformer

import fetch_s2_tiles as f

ROOT = Path(__file__).resolve().parents[1]
SRC, DST = ROOT / "data" / "kilns" / "yolo", ROOT / "data" / "kilns" / "yolo_ours"
PX, RES = 128, 10
TR = Transformer.from_crs(4326, 32643, always_xy=True)


def norm(b):
    return ((b - b.min()) / (b.max() - b.min() + 1e-5) * 255).astype(np.uint8)


def fetch(img, split: str, stem: str) -> str:
    out = DST / split / "images" / f"{stem}.png"
    if out.exists():
        return "skip"
    lat, lon = map(float, stem.split("_"))
    x, y = TR.transform(lon, lat)
    x0 = round((x - PX * RES / 2) / RES) * RES
    y0 = round((y + PX * RES / 2) / RES) * RES
    url = img.getDownloadURL({"format": "NPY", "crs": f.UTM,
                              "crs_transform": [RES, 0, x0, 0, -RES, y0], "dimensions": f"{PX}x{PX}"})
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=120)
            if r.ok:
                a = np.load(__import__("io").BytesIO(r.content))
                rgb = np.dstack([norm(a[b].astype(float)) for b in ("B4", "B3", "B2")])
                if (a["B4"] == 0).mean() > 0.2:
                    return "empty"
                Image.fromarray(rgb).save(out)
                lab = SRC / split / "labels" / f"{stem}.txt"
                (DST / split / "labels" / f"{stem}.txt").write_text(lab.read_text() if lab.exists() else "")
                return "ok"
        except Exception:
            pass
        time.sleep(3 * (attempt + 1))
    return "fail"


def main() -> None:
    ee.Initialize(project=f.PROJECT)
    img = f.composite("s2324")
    jobs = []
    for split in ("train", "val"):
        for sub in ("images", "labels"):
            (DST / split / sub).mkdir(parents=True, exist_ok=True)
        jobs += [(split, p.stem) for p in (SRC / split / "images").glob("*.png")]
    counts = {"ok": 0, "skip": 0, "fail": 0, "empty": 0}
    t0 = time.time()
    with ThreadPoolExecutor(8) as pool:
        futs = [pool.submit(fetch, img, s, st) for s, st in jobs]
        for i, fu in enumerate(as_completed(futs), 1):
            counts[fu.result()] += 1
            if i % 500 == 0 or i == len(futs):
                print(f"{i}/{len(futs)} {counts} {time.time() - t0:.0f}s", flush=True)
    (DST / "data.yaml").write_text(
        f"path: {DST.as_posix()}\ntrain: train/images\nval: val/images\n"
        "names:\n  0: CFCBK\n  1: FCBK\n  2: Zigzag\n", encoding="utf-8")


if __name__ == "__main__":
    main()
