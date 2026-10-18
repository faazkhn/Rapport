#!/usr/bin/env python3
"""Face exposure check for a lighting still (DESIGN v0.3 acceptance: face mean 0.45-0.60).

Usage:
    face_luminance.py STILL.png [--box x0 y0 x1 y1] [--min 0.45 --max 0.60]

The face box defaults to STILL.face.json, written by Unity's PsychSim/Capture Lighting Stills (projected eye/head bones).
Formula: Rec.709 relative luminance Y = 0.2126 R + 0.7152 G + 0.0722 B on sRGB-decoded (linear) pixel values in 0..1.
Rec.709 luma on the encoded values (Y') is printed alongside for reference.
Crushed / blown: % of all frame pixels with Y < 0.02 / Y > 0.98. Exit code 1 if the face mean is out of range.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

W = np.array([0.2126, 0.7152, 0.0722])


def measure(png, box=None):
    rgb = np.asarray(Image.open(png).convert("RGB"), dtype=np.float64) / 255.0
    if box is None:
        box = json.loads(Path(png).with_suffix(".face.json").read_text())["box"]
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    luma = rgb @ W
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4) @ W
    face = luma[y0:y1, x0:x1]
    assert face.size > 0, f"empty face box {box} for image {rgb.shape[1]}x{rgb.shape[0]}"
    return {
        "face_box": [x0, y0, x1, y1],
        "face_mean": float(lin[y0:y1, x0:x1].mean()),
        "face_mean_luma": float(face.mean()),
        "frame_mean": float(lin.mean()),
        "crushed_pct": float((lin < 0.02).mean() * 100),
        "blown_pct": float((lin > 0.98).mean() * 100),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("still")
    ap.add_argument("--box", nargs=4, type=float, metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--min", type=float, default=0.45)
    ap.add_argument("--max", type=float, default=0.60)
    a = ap.parse_args()
    r = measure(a.still, a.box)
    ok = a.min <= r["face_mean"] <= a.max
    print(f"{a.still}: face {r['face_mean']:.3f} (luma {r['face_mean_luma']:.3f}) box {r['face_box']} | "
          f"frame {r['frame_mean']:.3f} | crushed {r['crushed_pct']:.2f}% | blown {r['blown_pct']:.2f}% | "
          f"{'PASS' if ok else 'FAIL'} [{a.min}-{a.max}]")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
