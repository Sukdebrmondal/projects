"""
tests/test_crypto.py
Unit tests for RSA-1024 signatures and SHA-512 hashing.
Run from the project root:  python -m pytest -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from crypto_utils import (  # noqa: E402
    KEY_SIZE,
    generate_keys,
    sha512_hex,
    sign_data,
    verify_signature,
)

MESSAGE = b"Centre 03 - Krishnath College"


@pytest.fixture(scope="module")
def keys():
    """One fresh key pair for all tests in this file (does not touch keys/)."""
    return generate_keys()


def test_sha512_length():
    assert len(sha512_hex(b"abc")) == 128


def test_sha512_known_value():
    # Official SHA-512 test vector for "abc"
    assert sha512_hex(b"abc").startswith("ddaf35a193617aba")


def test_signature_length(keys):
    private_key, _ = keys
    assert len(sign_data(MESSAGE, private_key)) == KEY_SIZE // 8


def test_valid_signature(keys):
    private_key, public_key = keys
    sig = sign_data(MESSAGE, private_key)
    assert verify_signature(MESSAGE, sig, public_key) is True


def test_tampered_message_fails(keys):
    private_key, public_key = keys
    sig = sign_data(MESSAGE, private_key)
    assert verify_signature(b"Centre 01 - Krishnath College", sig, public_key) is False


def test_wrong_public_key_fails(keys):
    private_key, _ = keys
    _, other_public_key = generate_keys()
    sig = sign_data(MESSAGE, private_key)
    assert verify_signature(MESSAGE, sig, other_public_key) is False


def test_broken_signature_fails(keys):
    private_key, public_key = keys
    sig = sign_data(MESSAGE, private_key)
    assert verify_signature(MESSAGE, sig[:-10], public_key) is False