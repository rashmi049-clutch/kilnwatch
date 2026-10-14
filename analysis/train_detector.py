"""
Day 2 (step 10) - Fine-tune a YOLO oriented-box detector on the ring training set.

Choices:
  * yolo11n-obb (nano): the smallest model, because training runs on a 4-core
    CPU with 8 GB RAM. Accuracy cost is measured on the NCR test, not assumed.
  * imgsz 256: patches are 128 px and kilns ~10 x 5 px. Upsampling gives the
    detector's stride-8 feature map ~2 cells per kiln instead of ~1.
  * Augmentation: flips and 90-degree rotations only. Kilns have no fixed
    orientation, but colour and scale augmentation would distort the per-patch
    min-max stretch the imagery already carries.
  * patience 5: stop when validation mAP stops improving.

Run in the background; progress is written to runs/detect/<name>/results.csv.
"""

from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "kilns" / "yolo" / "data.yaml"
RUNS = ROOT / "runs"


def main() -> None:
    model = YOLO("yolo11n-obb.pt")
    model.train(
        data=str(DATA),
        imgsz=256,
        epochs=20,
        patience=5,
        batch=16,
        workers=2,
        device="cpu",
        project=str(RUNS),
        name="ring_v1",
        exist_ok=True,
        seed=42,
        # geometry-only augmentation
        fliplr=0.5, flipud=0.5, degrees=90,
        hsv_h=0.0, hsv_s=0.0, hsv_v=0.0, scale=0.0, mosaic=0.0, mixup=0.0,
        plots=True,
        verbose=False,
    )


if __name__ == "__main__":
    main()
