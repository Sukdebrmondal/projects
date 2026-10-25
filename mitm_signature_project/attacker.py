# attacker_app.py
# Backend for AMIT (Man-in-the-Middle attacker) - runs on port 5002
# Rahul sends to this server thinking it is Priya. Amit can watch,
# modify, forge, strip, drop or replay messages before they reach Priya.

import secrets
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
    "mode": "manual",        # "forward" | "auto" | "manual"
    "auto_find": "1122",     # auto mode: text to search
    "auto_replace": "9999",  # auto mode: replace with this
    "pending": [],           # manual mode: packets waiting for a decision
    "captured": [],          # every packet seen (used for replay)
    "events": [],            # attack activity shown in the UI
}
VALID_MODES = ("forward", "auto", "manual")
VALID_ACTIONS = ("forward", "modify", "forge", "strip", "drop")
MAX_ITEMS = 50

ACTION_TEXT = {
    "forward": "Forwarded without change",
    "modify": "Modified message (kept old signature)",
    "forge": "Modified message + signed with attacker key",
    "strip": "Modified message + removed signature",
}


def now():
    return datetime.now().strftime("%H:%M:%S")


def add_event(kind, text, status):
    """Add to the activity list. Call this while holding the lock."""
    state["events"].insert(0, {"time": now(), "kind": kind, "text": text, "status": status})
    del state["events"][MAX_ITEMS:]
    cu.log_event("ATTACKER", status, f"{kind}: {text}")


def forward_to_receiver(packet):
    """Send a packet to Priya and return her verification result."""
    try:
        response = requests.post(config.RECEIVER_URL + "/receive",
                                 json=packet, timeout=config.REQUEST_TIMEOUT)
        return response.json()
    except (requests.RequestException, ValueError):
        return {"status": "ERROR", "ok": False, "reason": "Receiver server is not reachable."}


def make_item(packet):
    return {
        "id": secrets.token_hex(4),
        "time": now(),
        "packet": packet,
        "signed": bool(packet.get("signature")),
        "signature_preview": cu.preview_signature(packet.get("signature")),
    }


# ---------- Page ----------
@app.route("/")
def index():
    return render_template("attacker.html")


# ---------- Network endpoint (Rahul sends here) ----------
@app.route("/relay", methods=["POST"])
def relay():
    packet = request.get_json(silent=True)
    if not isinstance(packet, dict):
        return jsonify({"sent": False}), 400

    item = make_item(packet)
    with lock:
        state["captured"].insert(0, item)
        del state["captured"][MAX_ITEMS:]
        mode = state["mode"]
        find, replace = state["auto_find"], state["auto_replace"]

        if mode == "manual":
            state["pending"].insert(0, item)
            add_event("intercept", f"Holding message: \"{packet.get('message', '')}\"", "HELD")
            return jsonify({"sent": True})   # Rahul thinks it was delivered

    # forward / auto mode
    to_send = dict(packet)
    message = str(to_send.get("message", ""))
    if mode == "auto" and find and find in message:
        to_send["message"] = message.replace(find, replace)
        kind, text = "auto-modify", f"Auto-changed to: \"{to_send['message']}\""
    else:
        kind, text = "forward", f"Forwarded: \"{message}\""

    result = forward_to_receiver(to_send)
    with lock:
        add_event(kind, text, result["status"])
    return jsonify({"sent": True})


# ---------- API for the UI ----------
@app.route("/api/state", methods=["GET"])
def get_state():
    with lock:
        return jsonify({
            "mode": state["mode"],
            "auto_find": state["auto_find"],
            "auto_replace": state["auto_replace"],
            "pending": list(state["pending"]),
            "captured": list(state["captured"]),
            "events": list(state["events"]),
        })


@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.get_json(silent=True) or {}
    with lock:
        if data.get("mode") in VALID_MODES:
            state["mode"] = data["mode"]
        if "auto_find" in data:
            state["auto_find"] = str(data["auto_find"])
        if "auto_replace" in data:
            state["auto_replace"] = str(data["auto_replace"])
        settings = {k: state[k] for k in ("mode", "auto_find", "auto_replace")}
    cu.log_event("ATTACKER", "SETTINGS", str(settings))
    return jsonify(settings)


@app.route("/api/action", methods=["POST"])
def take_action():
    """Manual mode: decide what to do with a held packet."""
    data = request.get_json(silent=True) or {}
    item_id = data.get("id")
    action = data.get("action")
    new_message = str(data.get("new_message", "")).strip()

    if action not in VALID_ACTIONS:
        return jsonify({"error": "Unknown action."}), 400
    if action in ("modify", "forge", "strip") and not new_message:
        return jsonify({"error": "Write the new message first."}), 400

    with lock:
        item = next((p for p in state["pending"] if p["id"] == item_id), None)
        if item is None:
            return jsonify({"error": "Packet not found in the pending list."}), 404
        state["pending"].remove(item)

    packet = dict(item["packet"])

    if action == "drop":
        with lock:
            add_event("drop", f"Dropped: \"{packet.get('message', '')}\"", "DROPPED")
        return jsonify({"status": "DROPPED", "ok": False,
                        "reason": "Message was blocked by the attacker. Priya never got it."})

    if action in ("modify", "forge", "strip"):
        packet["message"] = new_message
    if action == "forge":
        packet = cu.forge_signature(packet)
    if action == "strip":
        packet["signature"] = None

    result = forward_to_receiver(packet)
    with lock:
        add_event(action, f"{ACTION_TEXT[action]}: \"{packet.get('message', '')}\"", result["status"])
    return jsonify(result)


@app.route("/api/replay", methods=["POST"])
def replay():
    """Send an old captured packet again, exactly as it was."""
    data = request.get_json(silent=True) or {}
    with lock:
        item = next((c for c in state["captured"] if c["id"] == data.get("id")), None)
    if item is None:
        return jsonify({"error": "Captured packet not found."}), 404

    result = forward_to_receiver(dict(item["packet"]))
    with lock:
        add_event("replay", f"Replayed old packet: \"{item['packet'].get('message', '')}\"",
                  result["status"])
    return jsonify(result)


@app.route("/api/clear", methods=["POST"])
def clear():
    with lock:
        state["pending"].clear()
        state["captured"].clear()
        state["events"].clear()
    return jsonify({"cleared": True})


if __name__ == "__main__":
    print(f"[*] Amit (Attacker) running at http://{config.HOST}:{config.ATTACKER_PORT}")
    app.run(host=config.HOST, port=config.ATTACKER_PORT, debug=False)