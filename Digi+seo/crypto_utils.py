"""
crypto_utils.py
RSA-1024 digital signature (PSS padding) and SHA-512 hashing utilities.
"""
import hashlib
import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

# ---------------- Configuration ----------------
KEY_SIZE = 1024          # Demo size. Use 2048 or more for real-world security.
PUBLIC_EXPONENT = 65537  # Standard RSA public exponent

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEYS_DIR = os.path.join(BASE_DIR, "keys")
PRIVATE_KEY_PATH = os.path.join(KEYS_DIR, "private_key.pem")
PUBLIC_KEY_PATH = os.path.join(KEYS_DIR, "public_key.pem")


# ---------------- Hashing ----------------
def sha512_hex(data: bytes) -> str:
    """Return the SHA-512 hash of data as a 128-character hex string."""
    return hashlib.sha512(data).hexdigest()


# ---------------- Key management ----------------
def generate_keys():
    """Generate a new RSA key pair. Returns (private_key, public_key)."""
    private_key = rsa.generate_private_key(
        public_exponent=PUBLIC_EXPONENT,
        key_size=KEY_SIZE,
    )
    return private_key, private_key.public_key()


def save_keys(private_key, public_key):
    """Save both keys as PEM files inside the keys/ folder."""
    os.makedirs(KEYS_DIR, exist_ok=True)

    with open(PRIVATE_KEY_PATH, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    with open(PUBLIC_KEY_PATH, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))


def load_private_key(path: str = PRIVATE_KEY_PATH):
    """Load the private key (used only for signing)."""
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def load_public_key(path: str = PUBLIC_KEY_PATH):
    """Load the public key (used for verification)."""
    with open(path, "rb") as f:
        return serialization.load_pem_public_key(f.read())


# ---------------- Signing and verification ----------------
def _pss_padding():
    """PSS padding with SHA-512 (safer than old PKCS#1 v1.5)."""
    return padding.PSS(
        mgf=padding.MGF1(hashes.SHA512()),
        salt_length=padding.PSS.MAX_LENGTH,
    )


def sign_data(data: bytes, private_key) -> bytes:
    """Sign data with RSA + SHA-512. Returns a signature of KEY_SIZE/8 bytes."""
    return private_key.sign(data, _pss_padding(), hashes.SHA512())


def verify_signature(data: bytes, signature: bytes, public_key) -> bool:
    """Return True if the signature is valid for this data, otherwise False."""
    try:
        public_key.verify(signature, data, _pss_padding(), hashes.SHA512())
        return True
    except (InvalidSignature, ValueError):
        return False


# ---------------- Self-test ----------------
if __name__ == "__main__":
    print("Running crypto self-test...")
    priv, pub = generate_keys()

    message = b"Centre 03 - Krishnath College"
    sig = sign_data(message, priv)

    print("Key size         :", KEY_SIZE, "bits")
    print("Signature length :", len(sig), "bytes")
    print("SHA-512 (start)  :", sha512_hex(message)[:32], "...")
    print("Verify original  :", verify_signature(message, sig, pub))
    print("Verify tampered  :", verify_signature(b"Centre 01 - Krishnath College", sig, pub))

    _, other_pub = generate_keys()
    print("Verify wrong key :", verify_signature(message, sig, other_pub))