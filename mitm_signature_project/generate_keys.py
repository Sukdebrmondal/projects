# generate_keys.py
# Run this file ONCE to create Rahul's RSA private and public keys.

import os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import config


def generate_keys():
    os.makedirs(config.KEYS_DIR, exist_ok=True)

    # Safety check: do not overwrite old keys by mistake
    if os.path.exists(config.PRIVATE_KEY_PATH):
        answer = input("[!] Keys already exist. Overwrite them? (y/n): ").strip().lower()
        if answer != "y":
            print("[-] Cancelled. Old keys are kept.")
            return

    # Step 1: Create the RSA key pair
    print(f"[*] Generating {config.RSA_KEY_SIZE}-bit RSA key pair...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,          # standard value used everywhere
        key_size=config.RSA_KEY_SIZE,
    )
    public_key = private_key.public_key()

    # Step 2: Convert keys to PEM format (text format that can be saved)
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Step 3: Save keys to files
    with open(config.PRIVATE_KEY_PATH, "wb") as f:
        f.write(private_bytes)
    with open(config.PUBLIC_KEY_PATH, "wb") as f:
        f.write(public_bytes)

    print("[+] RSA keys generated successfully!")
    print(f"[+] Key size: {config.RSA_KEY_SIZE} bits")
    print("[+] Private key saved to:", config.PRIVATE_KEY_PATH)
    print("[+] Public key saved to: ", config.PUBLIC_KEY_PATH)
    print("[!] Keep the private key SECRET. Share only the public key.")


if __name__ == "__main__":
    generate_keys()