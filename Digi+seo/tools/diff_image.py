"""
tools/diff_image.py
Make a picture that shows exactly which pixels changed between the original
question paper and a stego copy (changed pixels are painted red).

Usage (from the project root):
    python tools/diff_image.py
    python tools/diff_image.py ORIGINAL.png COPY.png
Output:
    demo/difference_map.png   whole page, faded, changed pixels in red
    demo/difference_zoom.png  top-left corner enlarged 6 times
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from stego import load_image  # noqa: E402

ZOOM = 6


def main():
    if len(sys.argv) >= 3:
        original_path, copy_path = sys.argv[1], sys.argv[2]
    else:
        original_path = os.path.join(ROOT, "samples", "question_paper.png")
        copies = sorted(glob.glob(os.path.join(ROOT, "samples", "copies", "*.png")))
        if not copies:
            print("No copies found. Run 'python core.py' first.")
            return
        copy_path = copies[0]

    original = load_image(original_path)
    copy = load_image(copy_path)
    if original.shape != copy.shape:
        print("The two images have different sizes.")
        return

    changed = np.any(original != copy, axis=2)            # True where a pixel changed

    # Fade the page so the red marks stand out
    picture = (original.astype(np.float32) * 0.3 + 255 * 0.7).astype(np.uint8)
    picture[changed] = [255, 0, 0]

    out_dir = os.path.join(ROOT, "demo")
    os.makedirs(out_dir, exist_ok=True)
    Image.fromarray(picture).save(os.path.join(out_dir, "difference_map.png"))

    # Enlarge the top-left corner, where the hidden data is stored
    rows_with_changes = np.where(changed.any(axis=1))[0]
    last_row = int(rows_with_changes.max()) + 1 if rows_with_changes.size else 1
    corner = picture[: max(last_row + 5, 20), :300]
    zoom = Image.fromarray(corner).resize(
        (corner.shape[1] * ZOOM, corner.shape[0] * ZOOM), Image.NEAREST
    )
    zoom.save(os.path.join(out_dir, "difference_zoom.png"))

    total = changed.size
    print("Original :", os.path.relpath(original_path, ROOT))
    print("Copy     :", os.path.relpath(copy_path, ROOT))
    print(f"Changed pixels : {int(changed.sum())} out of {total} "
          f"({changed.sum() / total * 100:.4f}%)")
    print(f"Rows affected  : top {last_row} row(s) only")
    print("Saved: demo/difference_map.png and demo/difference_zoom.png")


if __name__ == "__main__":
    main()