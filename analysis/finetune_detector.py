"""
Domain-shift fix - fine-tune the ring detector on chips in our imagery style.

Starts from models/kiln_obb_ring_v1_best.pt (already knows kilns) and trains
5 epochs on data/kilns/yolo_ours, with a low learning rate and no warmup,
so it adapts to the seasonal-median look rather than relearning from scratch.
Same geometry-only augmentation as the first run.

Label noise is expected: dataset labels come from single scenes up to
Feb 2025, our chips from the Nov 2023 - Feb 2024 median, so kilns built in
between are labelled but not visible. Measured effect: NCR re-score (step 11).
"""

from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    model = YOLO(str(ROOT / "models" / "kiln_obb_ring_v1_best.pt"))
    model.train(
        data=str(ROOT / "data" / "kilns" / "yolo_ours" / "data.yaml"),
        imgsz=256, epochs=5, patience=3, batch=16, workers=2, device="cpu",
        lr0=0.002, lrf=0.2, warmup_epochs=0,
        project=str(ROOT / "runs"), name="ours_ft_v1", exist_ok=True, seed=42,
        fliplr=0.5, flipud=0.5, degrees=90,
        hsv_h=0.0, hsv_s=0.0, hsv_v=0.0, scale=0.0, mosaic=0.0, mixup=0.0,
        plots=True, verbose=False,
    )


if __name__ == "__main__":
    main()
