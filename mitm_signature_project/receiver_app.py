# receiver_app.py
# Backend for PRIYA (Receiver) - runs on port 5003
# Receives packets, verifies them, and keeps the results for the UI.

import threading
from datetime import datetime

from flask import Flask, jsonify, render_template, request

import config
import crypto_utils as cu

app = Flask(__name__)

# ---------- Server state (kept in memory) ----------
lock = threading.Lock()
replay_guard = cu.ReplayGuard()
state = {
    "secure_mode": True,                       # verify signatures or not
    "messages": [],                            # received messages (newest first)
    "stats": {"accepted": 0, "blocked": 0},
}
MAX_MESSAGES = 50


def now():
    return datetime.now().strftime("%H:%M:%S")


# ---------- Page ----------
@app.route("/")
def index():
    return render_template("receiver.html")


# ---------- Network endpoint ----------
@app.route("/receive", methods=["POST"])
def receive():
    """Packets arrive here. In our demo they come through the attacker."""
    packet = request.get_json(silent=True)
    if not isinstance(packet, dict):
        packet = {}

    with lock:
        result = cu.verify_packet(packet, replay_guard, secure_mode=state["secure_mode"])

        entry = {
            "time": now(),
            "sender": str(packet.get("sender", "?")),
            "message": str(packet.get("message", "")),
            "nonce": str(packet.get("nonce", "")),
            "signature": cu.preview_signature(packet.get("signature")),
            "status": result["status"],
            "ok": result["ok"],
            "reason": result["reason"],
            "secure_mode": state["secure_mode"],
        }
        state["messages"].insert(0, entry)
        del state["messages"][MAX_MESSAGES:]

        if result["ok"]:
            state["stats"]["accepted"] += 1
        else:
            state["stats"]["blocked"] += 1

    cu.log_event("RECEIVER", result["status"],
                 f"message='{entry['message']}' reason='{result['reason']}'")
    return jsonify(result)


# ---------- API for the UI ----------
@app.route("/api/state", methods=["GET"])
def get_state():
    with lock:
        return jsonify({
            "secure_mode": state["secure_mode"],
            "messages": list(state["messages"]),
            "stats": dict(state["stats"]),
        })


@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.get_json(silent=True) or {}
    with lock:
        if "secure_mode" in data:
            state["secure_mode"] = bool(data["secure_mode"])
        secure = state["secure_mode"]
    cu.log_event("RECEIVER", "SETTINGS", f"secure_mode={secure}")
    return jsonify({"secure_mode": secure})


@app.route("/api/clear", methods=["POST"])
def clear():
    with lock:
        state["messages"].clear()
        state["stats"] = {"accepted": 0, "blocked": 0}
        replay_guard.clear()
    return jsonify({"cleared": True})


if __name__ == "__main__":
    cu.load_public_key()   # stop early if keys are missing
    print(f"[*] Priya (Receiver) running at http://{config.HOST}:{config.RECEIVER_PORT}")
    app.run(host=config.HOST, port=config.RECEIVER_PORT, debug=False)