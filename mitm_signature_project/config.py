# config.py
# All project settings are kept here in one place.
# If you want to change a port or a time limit, change it ONLY here.

import os

# Base folder of the project (so file paths work from anywhere)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------- Network settings ----------
HOST = "127.0.0.1"

SENDER_PORT = 5001      # Rahul  (Sender)
ATTACKER_PORT = 5002    # Amit   (Man-in-the-Middle)
RECEIVER_PORT = 5003    # Priya  (Receiver)

# Rahul thinks he is talking to Priya, but his messages go to Amit first.
ATTACKER_URL = f"http://{HOST}:{ATTACKER_PORT}"
RECEIVER_URL = f"http://{HOST}:{RECEIVER_PORT}"

REQUEST_TIMEOUT = 5     # seconds to wait when one server calls another

# ---------- Security settings ----------
RSA_KEY_SIZE = 2048     # RSA key length in bits (2048 or 3072)
MESSAGE_MAX_AGE = 60    # messages older than 60 seconds are rejected
CLOCK_SKEW_ALLOWED = 5  # small clock difference allowed (seconds)

# ---------- Identity ----------
SENDER_NAME = "Rahul"

# ---------- File paths ----------
KEYS_DIR = os.path.join(BASE_DIR, "keys")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

PRIVATE_KEY_PATH = os.path.join(KEYS_DIR, "rahul_private.pem")
PUBLIC_KEY_PATH = os.path.join(KEYS_DIR, "rahul_public.pem")
LOG_FILE_PATH = os.path.join(LOGS_DIR, "security_log.txt")