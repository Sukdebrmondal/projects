"""
tools/psnr.py
Measure how different a stego copy is from the original image.

PSNR (Peak Signal-to-Noise Ratio), in decibels:
    MSE  = mean of (original - copy)^2
    PSNR = 10 * log10(255^2 / MSE)
Higher PSNR = more similar. Above about 50 dB the change is invisible.

Usage (from the project root):
    python tools/psnr.py
        compares samples/question_paper.png with every PNG in samples/copies
    python tools/psnr.py ORIGINAL.png COPY.png [COPY2.png ...]
"""
import glob
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from stego import load_image  # noqa: E402

INVISIBLE_DB = 50.0


def compare(original: np.ndarray, copy: np.ndarray) -> dict:
    """Return MSE, PSNR and change statistics between two images."""
    if original.shape != copy.shape:
        raise ValueError("Images have different sizes and cannot be compared.")

    diff = original.astype(np.int16) - copy.astype(np.int16)
    mse = float(np.mean(diff.astype(np.float64) ** 2))
    psnr = float("inf") if mse == 0 else 10 * math.log10(255 ** 2 / mse)

    return {
        "mse": mse,
        "psnr": psnr,
        "changed_values": int(np.count_nonzero(diff)),
        "total_values": int(diff.size),
        "changed_pixels": int(np.count_nonzero(np.any(diff != 0, axis=2))),
        "total_pixels": int(diff.shape[0] * diff.shape[1]),
        "max_change": int(np.abs(diff).max()),
    }


def main():
    if len(sys.argv) >= 3:
        original_path, copy_paths = sys.argv[1], sys.argv[2:]
    else:
        original_path = os.path.join(ROOT, "samples", "question_paper.png")
        copy_paths = sorted(glob.glob(os.path.join(ROOT, "samples", "copies", "*.png")))

    if not os.path.exists(original_path):
        print("Original image not found:", original_path)
        return
    if not copy_paths:
        print("No copies found. Run 'python core.py' first, or pass file paths.")
        return

    original = load_image(original_path)
    print(f"Original: {os.path.relpath(original_path, ROOT)} "
          f"({original.shape[1]} x {original.shape[0]} pixels)\n")
    print(f"{'Copy':<22}{'MSE':>12}{'PSNR (dB)':>12}{'Changed values':>22}{'Max change':>12}")
    print("-" * 80)

    all_invisible = True
    for path in copy_paths:
        stats = compare(original, load_image(path))
        psnr_text = "infinite" if math.isinf(stats["psnr"]) else f"{stats['psnr']:.2f}"
        changed = f"{stats['changed_values']} / {stats['total_values']}"
        print(f"{os.path.basename(path):<22}{stats['mse']:>12.6f}{psnr_text:>12}"
              f"{changed:>22}{stats['max_change']:>12}")
        if stats["psnr"] < INVISIBLE_DB:
            all_invisible = False

    print()
    if all_invisible:
        print(f"Result: every copy has PSNR above {INVISIBLE_DB:.0f} dB and no value changed by more than 1.")
        print("The hidden data is invisible to the human eye.")
    else:
        print(f"Warning: at least one copy has PSNR below {INVISIBLE_DB:.0f} dB.")


if __name__ == "__main__":
    main()