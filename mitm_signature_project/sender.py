# sender_app.py
# Backend for RAHUL (Sender) - runs on port 5001
# Creates messages, signs them, and sends them to "Priya".
# Rahul does not know that the address actually belongs to the attacker.

import threading
from datetime import datetime

import requests
from flask import Flask, jsonify, render_template, request

import config
import crypto_utils as cu

app = Flask(__name__)

# ---------- Server state ----------
lock = threading.Lock()
state = {
    "sign_enabled": True,   # add digital signature or not
    "sent": [],             # sent messages (newest first)
}
MAX_MESSAGES = 50
MAX_LENGTH = 500

# Rahul believes this address belongs to Priya. It actually belongs to Amit.
PRIYA_ADDRESS = config.ATTACKER_URL + "/relay"


def now():
    return datetime.now().strftime("%H:%M:%S")


# ---------- Page ----------
@app.route("/")
def index():
    return render_template("sender.html")


# ---------- API for the UI ----------
@app.route("/api/send", methods=["POST"])
def send_message():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({"error": "Message cannot be empty."}), 400
    if len(message) > MAX_LENGTH:
        return jsonify({"error": f"Message is too long (max {MAX_LENGTH} characters)."}), 400

    with lock:
        sign = state["sign_enabled"]

    packet = cu.create_packet(message, sign=sign)

    try:
        response = requests.post(PRIYA_ADDRESS, json=packet,
                                 timeout=config.REQUEST_TIMEOUT * 2)
        delivered = response.ok
    except requests.RequestException:
        delivered = False

    entry = {
        "time": now(),
        "message": message,
        "signed": sign,
        "signature": cu.preview_signature(packet["signature"]),
        "nonce": packet["nonce"],
        "timestamp": packet["timestamp"],
        "delivered": delivered,
    }
    with lock:
        state["sent"].insert(0, entry)
        del state["sent"][MAX_MESSAGES:]

    cu.log_event("SENDER", "SENT" if delivered else "FAILED",
                 f"message='{message}' signed={sign}")

    if not delivered:
        return jsonify({"error": "Could not reach Priya. Is the server running?",
                        "entry": entry}), 502
    return jsonify(entry)


@app.route("/api/state", methods=["GET"])
def get_state():
    with lock:
        return jsonify({"sign_enabled": state["sign_enabled"], "sent": list(state["sent"])})


@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.get_json(silent=True) or {}
    with lock:
        if "sign_enabled" in data:
            state["sign_enabled"] = bool(data["sign_enabled"])
        sign = state["sign_enabled"]
    cu.log_event("SENDER", "SETTINGS", f"sign_enabled={sign}")
    return jsonify({"sign_enabled": sign})


@app.route("/api/clear", methods=["POST"])
def clear():
    with lock:
        state["sent"].clear()
    return jsonify({"cleared": True})


if __name__ == "__main__":
    cu.load_private_key()   # stop early if keys are missing
    print(f"[*] Rahul (Sender) running at http://{config.HOST}:{config.SENDER_PORT}")
    app.run(host=config.HOST, port=config.SENDER_PORT, debug=False)