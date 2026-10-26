"""
core.py
Main logic: create signed copies for each centre and verify suspected copies.

Data hidden in each copy:
    PAYLOAD (JSON, UTF-8) + SIGNATURE (KEY_SIZE/8 bytes)
"""
import json
from datetime import datetime

from crypto_utils import KEY_SIZE, sign_data, verify_signature
from stego import embed_data, extract_data, image_hash

SIG_LEN = KEY_SIZE // 8           # 128 bytes for RSA-1024

STATUS_VALID = "valid"            # green: genuine copy, source found
STATUS_TAMPERED = "tampered"      # yellow: data found but signature/hash failed
STATUS_NO_DATA = "no_data"        # red: no hidden data from our system


# ---------------- Payload helpers ----------------
def make_copy_id(centre_id: int) -> str:
    """Example: centre 3 in year 2026 -> 'QP-26-03'."""
    return f"QP-{datetime.now():%y}-{centre_id:02d}"


def payload_to_bytes(payload: dict) -> bytes:
    """
    Convert payload to bytes in a fixed, repeatable way.
    sort_keys and compact separators make sure signing and verifying
    always use exactly the same bytes.
    """
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


# ---------------- Create a copy ----------------
def create_copy(pixels, centre_id: int, centre_name: str, copy_id: str,
                paper_name: str, private_key):
    """
    Build a signed payload for one centre and hide it in the image.
    Returns (stego_pixels, payload_dict).
    """
    payload = {
        "centre_id": centre_id,
        "centre_name": centre_name,
        "copy_id": copy_id,
        "paper_name": paper_name,
        "created_at": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "image_hash": image_hash(pixels),
    }

    payload_bytes = payload_to_bytes(payload)
    signature = sign_data(payload_bytes, private_key)
    stego_pixels = embed_data(pixels, payload_bytes + signature)
    return stego_pixels, payload


# ---------------- Verify a copy ----------------
def verify_copy(pixels, public_key) -> dict:
    """
    Check a suspected image. Returns a dict with:
    status, message, payload, signature_ok, hash_ok
    """
    result = {
        "status": STATUS_NO_DATA,
        "message": "No hidden data found. This image was not created by the system.",
        "payload": None,
        "signature_ok": False,
        "hash_ok": False,
    }

    # Step 1: extract hidden bytes
    data = extract_data(pixels)
    if data is None or len(data) <= SIG_LEN:
        return result

    # Step 2: split into payload and signature
    payload_bytes, signature = data[:-SIG_LEN], data[-SIG_LEN:]

    # Step 3: read the JSON payload
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return result
    if not isinstance(payload, dict):
        return result

    # Step 4: check signature and image hash
    signature_ok = verify_signature(payload_bytes, signature, public_key)
    hash_ok = payload.get("image_hash") == image_hash(pixels)

    result["payload"] = payload
    result["signature_ok"] = signature_ok
    result["hash_ok"] = hash_ok

    # Step 5: decide the final status
    if signature_ok and hash_ok:
        result["status"] = STATUS_VALID
        result["message"] = (
            f"Genuine copy. Source: Centre {payload.get('centre_id'):02d} - "
            f"{payload.get('centre_name')}"
        )
    else:
        problems = []
        if not signature_ok:
            problems.append("signature does not match (hidden data was forged or changed)")
        if not hash_ok:
            problems.append("image content was edited")
        result["status"] = STATUS_TAMPERED
        result["message"] = "Tampered copy: " + "; ".join(problems) + "."

    return result


# ---------------- Command-line demo ----------------
if __name__ == "__main__":
    import os
    import sys

    from crypto_utils import load_private_key, load_public_key
    from stego import load_image, save_image

    base = os.path.dirname(os.path.abspath(__file__))
    paper_path = os.path.join(base, "samples", "question_paper.png")
    photo_path = os.path.join(base, "samples", "random_photo.jpg")
    out_dir = os.path.join(base, "samples", "copies")

    try:
        private_key = load_private_key()
        public_key = load_public_key()
    except (FileNotFoundError, ValueError):
        print("Keys not found or broken. Run 'python setup_keys.py' first.")
        sys.exit(1)

    if not os.path.exists(paper_path):
        print("samples/question_paper.png not found. Add the sample image first.")
        sys.exit(1)

    centres = [
        (1, "Berhampore Girls College"),
        (2, "Murshidabad Adarsha Vidyalaya"),
        (3, "Krishnath College"),
        (4, "Jiaganj High School"),
    ]

    # ---- Create one copy per centre ----
    os.makedirs(out_dir, exist_ok=True)
    pixels = load_image(paper_path)
    print("Creating copies...")
    for centre_id, centre_name in centres:
        copy_id = make_copy_id(centre_id)
        stego_pixels, _ = create_copy(
            pixels, centre_id, centre_name, copy_id, "Physics 2026", private_key
        )
        save_image(stego_pixels, os.path.join(out_dir, f"{copy_id}.png"))
        print("  Created:", f"{copy_id}.png")

    # ---- Verify every copy (reloaded from disk) ----
    labels = {STATUS_VALID: "[GREEN] ", STATUS_TAMPERED: "[YELLOW]", STATUS_NO_DATA: "[RED]   "}

    print("\nVerifying copies...")
    for name in sorted(os.listdir(out_dir)):
        res = verify_copy(load_image(os.path.join(out_dir, name)), public_key)
        print(f"  {name:<14} {labels[res['status']]} {res['message']}")

    # ---- Verify an unknown photo ----
    if os.path.exists(photo_path):
        print("\nVerifying unknown photo...")
        res = verify_copy(load_image(photo_path), public_key)
        print(f"  random_photo.jpg {labels[res['status']]} {res['message']}")