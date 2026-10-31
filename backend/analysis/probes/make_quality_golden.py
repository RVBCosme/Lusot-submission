"""Test data for the phone's quality check (MS5 Task 10): golden scores from the server's own code.

Makes six synthetic RGB images (flat 30, flat 200, a checkerboard, a gradient, seeded noise
and a 3 x 5 odd size), encodes each as PNG, scores the bytes with quality.quality_scores,
and writes the pixels and the scores, rounded to 8 decimals, with the live cutoffs
(TUNING's, which quality_refusal uses), to app/src/lib/quality.golden.json, which
app/src/lib/quality.test.ts reads. tests/test_quality_golden.py checks the committed file is
what this writes now, so a retuned cutoff or a changed score can't go unseen. No photograph
is used, nothing is sent anywhere, and no pipeline code changes (C600).

Run from the repo root: uv run --directory backend/analysis python probes/make_quality_golden.py
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from lusot_analysis.pipeline.quality import quality_scores
from lusot_analysis.tuning import TUNING

OUT = Path(__file__).resolve().parents[3] / "app" / "src" / "lib" / "quality.golden.json"
W, H = 16, 12


def images() -> dict[str, np.ndarray]:
    """The six RGB images, each H x W x 3 uint8 (the odd one 3 x 5)."""
    ys, xs = np.mgrid[0:H, 0:W]
    checker = np.where((xs + ys) % 2 == 0, 230, 20).astype(np.uint8)
    gradient = np.stack([xs * 15, ys * 20, (xs + ys) * 8], axis=-1).clip(0, 255).astype(np.uint8)
    noise = np.random.default_rng(20261031).integers(0, 256, size=(H, W, 3), dtype=np.uint8)
    odd = np.random.default_rng(7).integers(0, 256, size=(3, 5, 3), dtype=np.uint8)
    return {
        "flat_30": np.full((H, W, 3), 30, dtype=np.uint8),
        "flat_200": np.full((H, W, 3), 200, dtype=np.uint8),
        "checkerboard": np.repeat(checker[:, :, None], 3, axis=2),
        "gradient": gradient,
        "noise": noise,
        "odd_3x5": odd,
    }


def build() -> dict:
    """The golden file's content: the live cutoffs and each image's pixels and scores."""
    cases = []
    for name, rgb in images().items():
        ok, png = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        if not ok:
            raise SystemExit(f"could not encode {name}")
        scores = quality_scores(png.tobytes())
        cases.append(
            {
                "name": name,
                "width": int(rgb.shape[1]),
                "height": int(rgb.shape[0]),
                "rgb": [int(v) for v in rgb.reshape(-1)],
                "brightness": round(scores.brightness, 8),
                "sharpness": round(scores.sharpness, 8),
            }
        )
    return {
        "brightness_min": TUNING.brightness_min,
        "sharpness_min": TUNING.sharpness_min,
        "cases": cases,
    }


def render(golden: dict) -> str:
    return json.dumps(golden, indent=1) + "\n"


def main() -> None:
    golden = build()
    OUT.write_text(render(golden), encoding="utf-8")
    print(f"wrote {len(golden['cases'])} cases")


if __name__ == "__main__":
    main()
