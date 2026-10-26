"""
stego.py
LSB (Least Significant Bit) steganography on PNG images using NumPy.

Hidden data layout inside the image LSBs:
    [ MAGIC (4 bytes) | LENGTH (4 bytes) | DATA (LENGTH bytes) ]
"""
import numpy as np
from PIL import Image

from crypto_utils import sha512_hex

MAGIC = b"QPLD"           # Marker meaning "Question Paper Leak Detector data"
HEADER_BYTES = 8          # 4 bytes MAGIC + 4 bytes LENGTH


# ---------------- Image input/output ----------------
def load_image(path_or_file) -> np.ndarray:
    """
    Open an image and return its pixels as a (height, width, 3) uint8 array.
    Transparent images (palette PNGs, RGBA screenshots) are placed on a
    white background first, so transparent areas become white, not black.
    """
    img = Image.open(path_or_file)

    if img.mode in ("P", "PA", "LA", "RGBA") or "transparency" in img.info:
        img = img.convert("RGBA")
        background = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(background, img)

    return np.array(img.convert("RGB"), dtype=np.uint8)

def save_image(pixels: np.ndarray, path_or_file):
    """Save pixels as a lossless PNG (JPG would destroy the hidden bits)."""
    Image.fromarray(pixels, "RGB").save(path_or_file, format="PNG")


# ---------------- Helpers ----------------
def capacity_bytes(pixels: np.ndarray) -> int:
    """How many data bytes this image can hide (1 bit per colour value)."""
    return pixels.size // 8 - HEADER_BYTES


def _bytes_to_bits(data: bytes) -> np.ndarray:
    """Convert bytes to an array of 0/1 bits (most significant bit first)."""
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def _bits_to_bytes(bits: np.ndarray) -> bytes:
    """Convert an array of 0/1 bits back to bytes."""
    return np.packbits(bits).tobytes()


# ---------------- Embed and extract ----------------
def embed_data(pixels: np.ndarray, data: bytes) -> np.ndarray:
    """Hide data in the LSBs of the image. Returns a NEW pixel array."""
    if len(data) > capacity_bytes(pixels):
        raise ValueError(
            f"Image too small: needs {len(data)} bytes, "
            f"can hold only {capacity_bytes(pixels)} bytes."
        )

    header = MAGIC + len(data).to_bytes(4, "big")
    bits = _bytes_to_bits(header + data)

    flat = pixels.flatten()                       # copy, original stays unchanged
    n = bits.size
    flat[:n] = (flat[:n] & 0xFE) | bits           # clear LSB, then set our bit
    return flat.reshape(pixels.shape)


def extract_data(pixels: np.ndarray):
    """Read hidden data from the LSBs. Returns bytes, or None if nothing found."""
    flat = pixels.reshape(-1)
    header_bits = HEADER_BYTES * 8

    if flat.size < header_bits:
        return None

    header = _bits_to_bytes(flat[:header_bits] & 1)
    if header[:4] != MAGIC:
        return None                               # not created by our system

    length = int.from_bytes(header[4:8], "big")
    if length == 0 or length > capacity_bytes(pixels):
        return None                               # corrupted or fake header

    data_bits = flat[header_bits: header_bits + length * 8] & 1
    return _bits_to_bytes(data_bits)


# ---------------- Image hash (ignores LSBs) ----------------
def image_hash(pixels: np.ndarray) -> str:
    """
    SHA-512 of the image with every LSB set to 0.
    Hiding data changes only LSBs, so this hash is the same before and after
    embedding, but changes if anyone edits the visible content.
    """
    cleared = pixels & 0xFE
    return sha512_hex(cleared.tobytes())


# ---------------- Self-test ----------------
if __name__ == "__main__":
    import os
    import sys

    base = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(base, "samples", "question_paper.png")
    out = os.path.join(base, "samples", "stego_test.png")

    if not os.path.exists(src):
        print("samples/question_paper.png not found. Add the sample image first.")
        sys.exit(1)

    pixels = load_image(src)
    print("Image size     :", pixels.shape[1], "x", pixels.shape[0], "pixels")
    print("Capacity       :", capacity_bytes(pixels), "bytes")

    secret = b"Hello from Centre 03"
    stego_pixels = embed_data(pixels, secret)
    save_image(stego_pixels, out)

    reloaded = load_image(out)
    recovered = extract_data(reloaded)
    changed = int(np.count_nonzero(pixels != stego_pixels))

    print("Recovered      :", recovered)
    print("Match          :", recovered == secret)
    print("Values changed :", changed, "out of", pixels.size)
    print("Hash unchanged :", image_hash(pixels) == image_hash(reloaded))