"""
tests/test_stego.py
Unit tests for LSB steganography.
Uses random synthetic images, so the tests do not depend on sample files.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from stego import (  # noqa: E402
    capacity_bytes,
    embed_data,
    extract_data,
    image_hash,
    load_image,
    save_image,
)


def make_image(height=100, width=100, seed=0):
    """Create a random RGB test image."""
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)


def test_embed_and_extract_roundtrip():
    pixels = make_image()
    secret = b"Hello from Centre 03"
    assert extract_data(embed_data(pixels, secret)) == secret


def test_original_image_not_modified():
    pixels = make_image()
    before = pixels.copy()
    embed_data(pixels, b"some data")
    assert np.array_equal(pixels, before)


def test_only_lsb_changes():
    pixels = make_image()
    stego = embed_data(pixels, b"x" * 500)
    diff = np.abs(stego.astype(int) - pixels.astype(int))
    assert diff.max() <= 1


def test_hash_unchanged_after_embedding():
    pixels = make_image()
    stego = embed_data(pixels, b"x" * 500)
    assert image_hash(pixels) == image_hash(stego)


def test_hash_changes_when_content_edited():
    pixels = make_image()
    stego = embed_data(pixels, b"x" * 500)
    edited = stego.copy()
    edited[50:60, 50:60] = 255 - edited[50:60, 50:60]   # visibly change a block
    assert image_hash(stego) != image_hash(edited)


def test_image_without_data_returns_none():
    assert extract_data(make_image(seed=42)) is None


def test_too_much_data_raises_error():
    small = make_image(10, 10)
    with pytest.raises(ValueError):
        embed_data(small, b"x" * (capacity_bytes(small) + 1))


def test_survives_png_save_and_reload(tmp_path):
    pixels = make_image()
    secret = b"PNG keeps every bit"
    path = tmp_path / "stego.png"
    save_image(embed_data(pixels, secret), path)
    assert extract_data(load_image(path)) == secret


def test_bengali_text_roundtrip():
    pixels = make_image()
    secret = "কৃষ্ণনাথ কলেজ".encode("utf-8")
    assert extract_data(embed_data(pixels, secret)).decode("utf-8") == "কৃষ্ণনাথ কলেজ"