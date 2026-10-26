"""
setup_keys.py
Run this ONCE to create the permanent RSA key pair in the keys/ folder.
If the key files are missing, empty, broken, or do not match each other,
new keys are created automatically.
"""
from crypto_utils import (
    KEY_SIZE,
    PRIVATE_KEY_PATH,
    PUBLIC_KEY_PATH,
    generate_keys,
    load_private_key,
    load_public_key,
    save_keys,
)


def keys_are_valid() -> bool:
    """True only if both key files load correctly AND belong to the same pair."""
    try:
        private_key = load_private_key()
        public_key = load_public_key()
    except (FileNotFoundError, ValueError, TypeError):
        return False

    # The public key stored on disk must match the private key's public part
    return private_key.public_key().public_numbers() == public_key.public_numbers()


def main():
    if keys_are_valid():
        print("Valid keys already exist. No new keys were created.")
        print("(Never replace them after creating copies: old copies would fail.)")
        return

    print("Key files are missing, empty, or broken. Creating new keys...")
    private_key, public_key = generate_keys()
    save_keys(private_key, public_key)

    if keys_are_valid():
        print(f"RSA-{KEY_SIZE} key pair created:")
        print("  Private key:", PRIVATE_KEY_PATH)
        print("  Public key :", PUBLIC_KEY_PATH)
        print("Keep the private key secret. Never upload it to GitHub.")
    else:
        print("Something went wrong while saving the keys.")


if __name__ == "__main__":
    main()