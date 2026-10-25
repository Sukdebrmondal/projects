# crypto_utils.py
# The "brain" of the project:
#   - Sender  : creates and signs packets (RSA-PSS + SHA-512)
#   - Attacker: forges signatures with his own key
#   - Receiver: verifies signature, freshness (timestamp) and nonce (replay)

import base64
import json
import os
import secrets
import time
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import config

# ---------- Verification status codes ----------
STATUS_VALID = "VALID"                # signature OK, fresh, not replayed
STATUS_UNVERIFIED = "UNVERIFIED"      # security OFF, nothing was checked
STATUS_NO_SIGNATURE = "NO_SIGNATURE"  # signature missing (or removed)
STATUS_TAMPERED = "TAMPERED"          # signature does not match
STATUS_EXPIRED = "EXPIRED"            # message too old / from the future
STATUS_REPLAY = "REPLAY"              # same nonce seen before
STATUS_BAD_FORMAT = "BAD_FORMAT"      # broken packet

# These fields are protected by the signature
SIGNED_FIELDS = ("sender", "message", "timestamp", "nonce")


# =====================================================================
#  Key loading
# =====================================================================
_private_key = None
_public_key = None
_attacker_key = None


def load_private_key():
    """Load Rahul's private key (used only by the sender)."""
    global _private_key
    if _private_key is None:
        if not os.path.exists(config.PRIVATE_KEY_PATH):
            raise FileNotFoundError("Private key not found. Run generate_keys.py first.")
        with open(config.PRIVATE_KEY_PATH, "rb") as f:
            _private_key = serialization.load_pem_private_key(f.read(), password=None)
    return _private_key


def load_public_key():
    """Load Rahul's public key (used by the receiver to verify)."""
    global _public_key
    if _public_key is None:
        if not os.path.exists(config.PUBLIC_KEY_PATH):
            raise FileNotFoundError("Public key not found. Run generate_keys.py first.")
        with open(config.PUBLIC_KEY_PATH, "rb") as f:
            _public_key = serialization.load_pem_public_key(f.read())
    return _public_key


def get_attacker_key():
    """The attacker's OWN key. He does NOT have Rahul's private key."""
    global _attacker_key
    if _attacker_key is None:
        _attacker_key = rsa.generate_private_key(
            public_exponent=65537, key_size=config.RSA_KEY_SIZE
        )
    return _attacker_key


# =====================================================================
#  Helper functions
# =====================================================================
def _pss_padding():
    """RSA-PSS padding using SHA-512."""
    return padding.PSS(
        mgf=padding.MGF1(hashes.SHA512()),
        salt_length=padding.PSS.MAX_LENGTH,
    )


def get_signing_data(packet):
    """Build the exact bytes that are signed (same order every time)."""
    data = {field: packet[field] for field in SIGNED_FIELDS}
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


def sign_data(data, private_key):
    """Sign bytes with RSA-PSS + SHA-512 and return Base64 text."""
    signature = private_key.sign(data, _pss_padding(), hashes.SHA512())
    return base64.b64encode(signature).decode("ascii")


def preview_signature(signature_b64, length=40):
    """Short version of the signature for showing in the UI."""
    if not signature_b64:
        return "(no signature)"
    return signature_b64[:length] + "..."


# =====================================================================
#  Sender side (Rahul)
# =====================================================================
def create_packet(message, sign=True, timestamp=None):
    """Create a message packet. If sign=True, add Rahul's digital signature."""
    packet = {
        "sender": config.SENDER_NAME,
        "message": message,
        "timestamp": int(timestamp if timestamp is not None else time.time()),
        "nonce": secrets.token_hex(8),   # random one-time number
        "signature": None,
    }
    if sign:
        packet["signature"] = sign_data(get_signing_data(packet), load_private_key())
    return packet


# =====================================================================
#  Attacker side (Amit)
# =====================================================================
def forge_signature(packet):
    """Attacker re-signs the packet with HIS OWN key (not Rahul's)."""
    forged = dict(packet)
    forged["signature"] = sign_data(get_signing_data(forged), get_attacker_key())
    return forged


# =====================================================================
#  Receiver side (Priya)
# =====================================================================
class ReplayGuard:
    """Remembers nonces that were already used, to stop replay attacks."""

    def __init__(self):
        self.seen = {}   # nonce -> timestamp

    def is_replay(self, nonce):
        return nonce in self.seen

    def remember(self, nonce, timestamp):
        self.seen[nonce] = timestamp
        self._cleanup()

    def clear(self):
        self.seen.clear()

    def _cleanup(self):
        # Old nonces can be forgotten: old messages are rejected as EXPIRED anyway
        limit = time.time() - config.MESSAGE_MAX_AGE * 2
        self.seen = {n: t for n, t in self.seen.items() if t >= limit}


def _result(status, reason):
    accepted = status in (STATUS_VALID, STATUS_UNVERIFIED)
    return {"status": status, "ok": accepted, "reason": reason}


def verify_packet(packet, replay_guard, secure_mode=True):
    """Check a received packet. Returns a dict: status, ok, reason."""

    # Check 1: Is the packet complete?
    if not isinstance(packet, dict) or any(f not in packet for f in SIGNED_FIELDS):
        return _result(STATUS_BAD_FORMAT, "Packet is broken or missing fields.")

    # Security OFF: accept everything without checking (unsafe system)
    if not secure_mode:
        return _result(STATUS_UNVERIFIED, "Security is OFF. Message accepted without any check.")

    # Check 2: Is there a signature?
    signature_b64 = packet.get("signature")
    if not signature_b64:
        return _result(STATUS_NO_SIGNATURE, "Message has no digital signature. Rejected.")

    # Check 3: Is the signature valid? (RSA-PSS + SHA-512)
    try:
        signature = base64.b64decode(signature_b64, validate=True)
        load_public_key().verify(
            signature, get_signing_data(packet), _pss_padding(), hashes.SHA512()
        )
    except (InvalidSignature, ValueError, TypeError):
        return _result(
            STATUS_TAMPERED,
            "Signature does not match. Message was modified or not signed by Rahul.",
        )

    # Check 4: Is the message fresh? (timestamp)
    age = time.time() - packet["timestamp"]
    if age > config.MESSAGE_MAX_AGE:
        return _result(STATUS_EXPIRED, f"Message is too old ({int(age)} seconds). Possible replay attack.")
    if age < -config.CLOCK_SKEW_ALLOWED:
        return _result(STATUS_EXPIRED, "Message time is in the future. Rejected.")

    # Check 5: Was this message seen before? (nonce)
    if replay_guard.is_replay(packet["nonce"]):
        return _result(STATUS_REPLAY, "This message was already received. Replay attack detected.")

    replay_guard.remember(packet["nonce"], packet["timestamp"])
    return _result(STATUS_VALID, "Signature verified. Message is authentic and fresh.")


# =====================================================================
#  Logging
# =====================================================================
def log_event(role, status, details):
    """Save a security event to logs/security_log.txt"""
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{time_str}] [{role}] [{status}] {details}\n"
    with open(config.LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(line)


# =====================================================================
#  Self-test: run "python crypto_utils.py" to check everything works
# =====================================================================
def run_self_test():
    print("=" * 64)
    print("  crypto_utils.py SELF-TEST  (RSA-PSS + SHA-512)")
    print("=" * 64)

    guard = ReplayGuard()
    passed = 0
    total = 0

    def check(title, result, expected):
        nonlocal passed, total
        total += 1
        mark = "PASS" if result["status"] == expected else "FAIL"
        if mark == "PASS":
            passed += 1
        print(f"[{mark}] {title}")
        print(f"       Status : {result['status']}  (expected {expected})")
        print(f"       Reason : {result['reason']}\n")

    # Test 1: Genuine message
    original = create_packet("Send 5000 rupees to account 1122")
    raw_sig = base64.b64decode(original["signature"])
    print(f"Signature size: {len(raw_sig)} bytes")
    print(f"Signature preview: {preview_signature(original['signature'])}\n")
    check("1. Genuine signed message", verify_packet(original, guard), STATUS_VALID)

    # Test 2: Attacker changes the message
    tampered = create_packet("Send 5000 rupees to account 1122")
    tampered["message"] = "Send 50000 rupees to account 9999"
    check("2. Message modified by attacker", verify_packet(tampered, guard), STATUS_TAMPERED)

    # Test 3: Attacker signs with his own key
    forged = forge_signature(tampered)
    check("3. Signed with attacker's own key", verify_packet(forged, guard), STATUS_TAMPERED)

    # Test 4: Attacker sends the old genuine message again
    check("4. Replay of the genuine message", verify_packet(original, guard), STATUS_REPLAY)

    # Test 5: Attacker removes the signature
    stripped = create_packet("Send 5000 rupees to account 1122")
    stripped["signature"] = None
    check("5. Signature removed by attacker", verify_packet(stripped, guard), STATUS_NO_SIGNATURE)

    # Test 6: Old message (2 minutes old)
    old = create_packet("Send 5000 rupees to account 1122", timestamp=time.time() - 120)
    check("6. Old message (120 seconds)", verify_packet(old, guard), STATUS_EXPIRED)

    # Test 7: Security OFF -> tampered message is accepted (shows the danger)
    check("7. Security OFF + modified message",
          verify_packet(tampered, guard, secure_mode=False), STATUS_UNVERIFIED)

    print("=" * 64)
    print(f"  RESULT: {passed}/{total} tests passed")
    print("=" * 64)


if __name__ == "__main__":
    run_self_test()