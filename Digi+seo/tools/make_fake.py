"""
tools/make_fake.py
Forgery test: take a genuine copy, change the hidden centre to an innocent
centre, and re-sign with an ATTACKER's key (the attacker does not have the
real private key). The system should detect this as TAMPERED.

Usage (from the project root):
    python tools/make_fake.py
    python tools/make_fake.py samples/copies/QP-26-03.png
"""
import glob
import json
import os
import sys

# Allow importing modules from the project root folder
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import SIG_LEN, payload_to_bytes, verify_copy  # noqa: E402
from crypto_utils import generate_keys, load_public_key, sign_data  # noqa: E402
from stego import embed_data, extract_data, load_image, save_image  # noqa: E402


def main():
    # Pick the source copy: from the command line, or the third copy by default
    if len(sys.argv) > 1:
        source = sys.argv[1]
    else:
        copies = sorted(glob.glob(os.path.join(ROOT, "samples", "copies", "*.png")))
        if len(copies) < 3:
            print("Run 'python core.py' first to create the copies.")
            return
        source = copies[2]

    pixels = load_image(source)
    data = extract_data(pixels)
    if data is None:
        print("The source image has no hidden data.")
        return

    # Read the genuine payload
    payload = json.loads(data[:-SIG_LEN].decode("utf-8"))
    print("Genuine centre :", payload["centre_id"], "-", payload["centre_name"])

    # Attacker changes the centre to frame an innocent centre
    payload["centre_id"] = 1
    payload["centre_name"] = "Berhampore Girls College"
    print("Forged centre  :", payload["centre_id"], "-", payload["centre_name"])

    # Attacker signs with their OWN key (they don't have the real private key)
    attacker_private_key, _ = generate_keys()
    fake_bytes = payload_to_bytes(payload)
    fake_signature = sign_data(fake_bytes, attacker_private_key)

    fake_pixels = embed_data(pixels, fake_bytes + fake_signature)
    out = os.path.join(ROOT, "samples", "fake_centre.png")
    save_image(fake_pixels, out)
    print("Saved forged image:", out)

    # Verify the forged image with the REAL public key
    result = verify_copy(load_image(out), load_public_key())
    print("\nVerification result:", result["status"].upper())
    print(result["message"])


if __name__ == "__main__":
    main()