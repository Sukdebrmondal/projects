"""
tests/test_app.py
Tests for the Flask website using Flask's built-in test client.

Every test uses a temporary database, a temporary ZIP folder and fresh RSA keys,
so the real leak_detector.db, generated/ and keys/ are never touched.
Run from the project root:  python -m pytest -v
"""
import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from PIL import Image  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
import database as db  # noqa: E402
from core import create_copy  # noqa: E402
from crypto_utils import generate_keys  # noqa: E402

ADMIN_USER = "admin"
ADMIN_PASS = "secret123"
MULTIPART = "multipart/form-data"


# ---------------- Helpers ----------------
def random_pixels(seed=0, width=200, height=200):
    """A random RGB test image as a NumPy array."""
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)


def image_file(pixels, fmt="PNG"):
    """Turn pixels into an in-memory image file (PNG or JPEG)."""
    buffer = io.BytesIO()
    Image.fromarray(pixels).save(buffer, format=fmt)
    buffer.seek(0)
    return buffer


def login(client, password=ADMIN_PASS):
    return client.post(
        "/login",
        data={"username": ADMIN_USER, "password": password},
        follow_redirects=True,
    )


def generate(client, centres="Krishnath College\nJiaganj High School",
             filename="paper.png", fmt="PNG", pixels=None):
    """Submit the 'Create copies' form."""
    if pixels is None:
        pixels = random_pixels()
    return client.post(
        "/generate",
        data={
            "paper_name": "Physics 2026",
            "centres": centres,
            "paper": (image_file(pixels, fmt), filename),
        },
        content_type=MULTIPART,
    )


def verify(client, file_obj, filename):
    """Submit the 'Verify a leak' form."""
    return client.post(
        "/verify",
        data={"image": (file_obj, filename)},
        content_type=MULTIPART,
    )


def first_copy_from_zip(client, paper_id=1):
    """Download the ZIP and return (file name, PNG bytes) of the first copy."""
    response = client.get(f"/download/{paper_id}")
    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        name = sorted(zf.namelist())[0]
        data = zf.read(name)
    response.close()
    return name, data


# ---------------- Fixture ----------------
@pytest.fixture
def client(tmp_path, monkeypatch):
    """A test client with a temporary database, folder and keys."""
    generated = tmp_path / "generated"
    generated.mkdir()

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(app_module, "GENERATED_DIR", str(generated))

    private_key, public_key = generate_keys()
    monkeypatch.setattr(app_module, "PRIVATE_KEY", private_key)
    monkeypatch.setattr(app_module, "PUBLIC_KEY", public_key)

    db.init_db()
    db.save_admin(ADMIN_USER, generate_password_hash(ADMIN_PASS))

    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as test_client:
        yield test_client


# ================= Public pages =================
def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Find out where a leaked question paper came from" in response.data


def test_verify_page_is_public(client):
    assert client.get("/verify").status_code == 200


def test_unknown_page_shows_404(client):
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404
    assert b"Page not found" in response.data


# ================= Login and security =================
@pytest.mark.parametrize("url", ["/generate", "/records", "/download/1"])
def test_admin_pages_need_login(client, url):
    response = client.get(url)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_wrong_password_is_rejected(client):
    response = login(client, password="wrong-pass")
    assert b"Wrong username or password." in response.data


def test_correct_login_opens_generate_page(client):
    response = login(client)
    assert b"Welcome, admin." in response.data
    assert b"Create signed copies" in response.data


def test_logout_blocks_admin_pages(client):
    login(client)
    client.get("/logout")
    assert client.get("/records").status_code == 302


def test_login_blocks_external_redirect(client):
    response = client.post(
        "/login?next=//evil.example.com",
        data={"username": ADMIN_USER, "password": ADMIN_PASS},
    )
    assert response.status_code == 302
    assert "evil.example.com" not in response.headers["Location"]


# ================= Create copies =================
def test_generate_creates_copies_zip_and_records(client):
    login(client)
    response = generate(client)
    assert response.status_code == 200
    assert b"2 signed copies are ready" in response.data

    zip_file = os.path.join(app_module.GENERATED_DIR, "paper_001.zip")
    with zipfile.ZipFile(zip_file) as zf:
        names = zf.namelist()
    assert len(names) == 2
    assert all(name.endswith(".png") for name in names)
    assert len(db.list_copies()) == 2


def test_duplicate_centres_are_skipped(client):
    login(client)
    response = generate(client, centres="Krishnath College\nkrishnath college\n\nJiaganj High School")
    assert b"2 signed copies are ready" in response.data


def test_generate_rejects_jpg(client):
    login(client)
    response = generate(client, filename="paper.jpg", fmt="JPEG")
    assert b"Unsupported file type" in response.data
    assert db.list_copies() == []


def test_generate_needs_centres(client):
    login(client)
    response = generate(client, centres="   \n   ")
    assert b"Enter at least one exam centre" in response.data


def test_generate_rejects_too_small_image(client):
    login(client)
    response = generate(client, pixels=random_pixels(width=10, height=10))
    assert b"The image is too small" in response.data


def test_download_returns_valid_zip(client):
    login(client)
    generate(client)
    response = client.get("/download/1")
    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        assert len(zf.namelist()) == 2
    response.close()


# ================= Verify a leak =================
def test_verify_genuine_copy_from_website(client):
    login(client)
    generate(client)
    name, data = first_copy_from_zip(client)
    client.get("/logout")                         # verification works without login

    response = verify(client, io.BytesIO(data), name)
    assert b"Genuine copy - source identified" in response.data
    assert b">Found<" in response.data


def test_verify_detects_forged_copy(client):
    attacker_key, _ = generate_keys()             # attacker does not have the real key
    forged, _ = create_copy(random_pixels(5), 1, "Innocent Centre",
                            "QP-FAKE", "Physics 2026", attacker_key)
    response = verify(client, image_file(forged), "forged.png")
    assert b"Tampered copy - this data cannot be trusted" in response.data


def test_verify_detects_edited_paper(client):
    login(client)
    generate(client)
    name, data = first_copy_from_zip(client)

    edited = np.array(Image.open(io.BytesIO(data)).convert("RGB"))
    edited[150:160, 50:100] = 255 - edited[150:160, 50:100]   # change visible content

    response = verify(client, image_file(edited), name)
    assert b"Tampered copy - this data cannot be trusted" in response.data
    assert b"Edited</span>" in response.data


def test_verify_unknown_image_has_no_data(client):
    response = verify(client, image_file(random_pixels(9)), "photo.png")
    assert b"No hidden data found" in response.data


def test_verify_jpeg_explains_compression(client):
    response = verify(client, image_file(random_pixels(9), "JPEG"), "photo.jpg")
    assert b"No hidden data found" in response.data
    assert b"This is a JPG image" in response.data


def test_verify_rejects_file_that_is_not_an_image(client):
    response = verify(client, io.BytesIO(b"hello, I am not an image"), "notes.png")
    assert b"This file is not a valid image." in response.data


def test_verify_rejects_wrong_file_type(client):
    response = verify(client, io.BytesIO(b"some text"), "notes.txt")
    assert b"Unsupported file type" in response.data