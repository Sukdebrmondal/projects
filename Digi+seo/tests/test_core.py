"""
tests/test_core.py
End-to-end tests: create copies, verify them, and detect forgery/editing.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from core import (  # noqa: E402
    SIG_LEN,
    STATUS_NO_DATA,
    STATUS_TAMPERED,
    STATUS_VALID,
    create_copy,
    make_copy_id,
    payload_to_bytes,
    verify_copy,
)
from crypto_utils import generate_keys, sign_data  # noqa: E402
from stego import embed_data, extract_data, load_image, save_image  # noqa: E402


@pytest.fixture(scope="module")
def keys():
    return generate_keys()


@pytest.fixture
def pixels():
    rng = np.random.default_rng(7)
    return rng.integers(0, 256, size=(200, 200, 3), dtype=np.uint8)


def make(pixels, private_key, centre_id=3, name="Krishnath College"):
    stego, _ = create_copy(
        pixels, centre_id, name, make_copy_id(centre_id), "Physics 2026", private_key
    )
    return stego


def test_copy_id_format():
    copy_id = make_copy_id(3)
    assert copy_id.startswith("QP-") and copy_id.endswith("-03")


def test_genuine_copy_is_valid(keys, pixels):
    private_key, public_key = keys
    result = verify_copy(make(pixels, private_key), public_key)
    assert result["status"] == STATUS_VALID
    assert result["payload"]["centre_id"] == 3
    assert result["payload"]["centre_name"] == "Krishnath College"


def test_each_centre_gets_its_own_data(keys, pixels):
    private_key, public_key = keys
    for centre_id in (1, 2, 3, 4):
        stego = make(pixels, private_key, centre_id, f"Centre {centre_id}")
        assert verify_copy(stego, public_key)["payload"]["centre_id"] == centre_id


def test_forged_centre_is_detected(keys, pixels):
    private_key, public_key = keys
    stego = make(pixels, private_key)

    data = extract_data(stego)
    payload = json.loads(data[:-SIG_LEN].decode("utf-8"))
    payload["centre_id"] = 1                                # attacker frames centre 1

    attacker_key, _ = generate_keys()
    fake_bytes = payload_to_bytes(payload)
    forged = embed_data(stego, fake_bytes + sign_data(fake_bytes, attacker_key))

    result = verify_copy(forged, public_key)
    assert result["status"] == STATUS_TAMPERED
    assert result["signature_ok"] is False
    assert result["hash_ok"] is True


def test_edited_question_is_detected(keys, pixels):
    private_key, public_key = keys
    stego = make(pixels, private_key)
    edited = stego.copy()
    edited[150:160, 50:100] = 255 - edited[150:160, 50:100]  # change visible content

    result = verify_copy(edited, public_key)
    assert result["status"] == STATUS_TAMPERED
    assert result["signature_ok"] is True
    assert result["hash_ok"] is False


def test_unknown_image_has_no_data(keys, pixels):
    _, public_key = keys
    assert verify_copy(pixels, public_key)["status"] == STATUS_NO_DATA


def test_wrong_public_key_is_tampered(keys, pixels):
    private_key, _ = keys
    _, other_public_key = generate_keys()
    result = verify_copy(make(pixels, private_key), other_public_key)
    assert result["status"] == STATUS_TAMPERED


def test_survives_png_save(keys, pixels, tmp_path):
    private_key, public_key = keys
    path = tmp_path / "copy.png"
    save_image(make(pixels, private_key), path)
    assert verify_copy(load_image(path), public_key)["status"] == STATUS_VALID


def test_bengali_centre_name(keys, pixels):
    private_key, public_key = keys
    stego = make(pixels, private_key, 3, "কৃষ্ণনাথ কলেজ")
    result = verify_copy(stego, public_key)
    assert result["status"] == STATUS_VALID
    assert result["payload"]["centre_name"] == "কৃষ্ণনাথ কলেজ"