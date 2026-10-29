#!/usr/bin/env python3
"""Reproduce the ClearFrame quality measurements published in docs/quality-report.md.

Each image in docs/benchmark-images/ is treated as ground truth at 720x1080,
downscaled to 360x540, upscaled 2x by the real pipeline, and compared with the
ground truth. Requires the backend installed by scripts/install_backend.py.

    python docs/benchmark.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clearframe.core import _model_result  # noqa: E402

IMAGES = ROOT / "docs" / "benchmark-images"
OUT = ROOT / "docs" / "benchmark-output"
RUNTIME = Path(__import__("os").environ.get("CLEARFRAME_RUNTIME", ROOT / ".runtime"))
ENGINE = RUNTIME / ("realesrgan-ncnn-vulkan.exe" if sys.platform.startswith("win") else "realesrgan-ncnn-vulkan")
MODELS = RUNTIME / "models"
TARGET = (720, 1080)
LR_SIZE = (360, 540)


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))
    return float("inf") if mse == 0 else 10.0 * np.log10(255.0 ** 2 / mse)


def _box(x: np.ndarray, size: int = 7) -> np.ndarray:
    pad = size // 2
    padded = np.pad(x, pad, mode="reflect")
    csum = np.pad(padded.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    total = csum[size:, size:] - csum[:-size, size:] - csum[size:, :-size] + csum[:-size, :-size]
    return total / (size * size)


def ssim(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a.astype(np.float64), b.astype(np.float64)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mu_a, mu_b = _box(a), _box(b)
    var_a, var_b = _box(a * a) - mu_a ** 2, _box(b * b) - mu_b ** 2
    cov = _box(a * b) - mu_a * mu_b
    return float(np.mean(((2 * mu_a * mu_b + c1) * (2 * cov + c2)) /
                         ((mu_a ** 2 + mu_b ** 2 + c1) * (var_a + var_b + c2))))


def luma(im: Image.Image) -> np.ndarray:
    return np.asarray(im.convert("L"))


def detail(im: Image.Image) -> float:
    g = luma(im).astype(np.float32)
    lap = 4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return float(np.mean(np.abs(lap)))


def main() -> int:
    if not ENGINE.is_file():
        print("Backend belum terpasang. Jalankan: python scripts/install_backend.py", file=sys.stderr)
        return 2
    OUT.mkdir(exist_ok=True)
    work = OUT / "work"
    work.mkdir(exist_ok=True)
    report = []
    for gt_path in sorted(IMAGES.glob("*_gt.png")):
        name = gt_path.stem.removesuffix("_gt")
        gt = Image.open(gt_path).convert("RGB").resize(TARGET, Image.Resampling.LANCZOS)
        lr = gt.resize(LR_SIZE, Image.Resampling.LANCZOS)
        lr.save(OUT / f"{name}_input.png")
        started = time.perf_counter()
        ai = _model_result(ENGINE, MODELS, lr, 2, work, name)
        seconds = time.perf_counter() - started
        baseline = lr.resize(TARGET, Image.Resampling.LANCZOS)
        gt_l = luma(gt)
        rows = []
        for label, im in (("lanczos", baseline),
                          ("ai_15", Image.blend(baseline, ai, 0.15)),
                          ("ai_30", Image.blend(baseline, ai, 0.30)),
                          ("ai_50", Image.blend(baseline, ai, 0.50)),
                          ("ai_100", ai)):
            im.save(OUT / f"{name}_{label}.png")
            rows.append({"variant": label, "ssim": round(ssim(luma(im), gt_l), 5),
                         "psnr_db": round(psnr(luma(im), gt_l), 2),
                         "detail": round(detail(im), 3)})
        report.append({"image": name, "seconds": round(seconds, 1), "variants": rows})
        print(json.dumps(report[-1]), flush=True)
    (OUT / "report.json").write_text(json.dumps(report, indent=2))
    print("saved", OUT / "report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
