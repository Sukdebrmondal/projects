# test_flow.py
# Full system test. All 3 servers must be running before you run this.

import requests
import config

SENDER = f"http://{config.HOST}:{config.SENDER_PORT}"
ATTACKER = config.ATTACKER_URL
RECEIVER = config.RECEIVER_URL

GENUINE = "Send 5000 rupees to account 1122"
FAKE = "Send 50000 rupees to account 9999"

passed = 0
total = 0


def post(url, data=None):
    return requests.post(url, json=data or {}, timeout=15).json()


def get(url):
    return requests.get(url, timeout=15).json()


def setup(sign, secure, mode):
    post(SENDER + "/api/settings", {"sign_enabled": sign})
    post(RECEIVER + "/api/settings", {"secure_mode": secure})
    post(ATTACKER + "/api/settings", {"mode": mode, "auto_find": "1122", "auto_replace": "9999"})


def last_received():
    messages = get(RECEIVER + "/api/state")["messages"]
    return messages[0] if messages else {"status": "NONE", "message": ""}


def first_pending_id():
    return get(ATTACKER + "/api/state")["pending"][0]["id"]


def check(title, status, expected, note=""):
    global passed, total
    total += 1
    mark = "PASS" if status == expected else "FAIL"
    if mark == "PASS":
        passed += 1
    print(f"[{mark}] {title}")
    print(f"       Priya's result: {status}  (expected {expected})")
    if note:
        print(f"       {note}")
    print()


def main():
    print("=" * 64)
    print("  FULL SYSTEM TEST  (Rahul -> Amit -> Priya)")
    print("=" * 64)

    for name, url in (("Sender", SENDER), ("Attacker", ATTACKER), ("Receiver", RECEIVER)):
        try:
            get(url + "/api/state")
        except requests.RequestException:
            print(f"[!] {name} server is not running at {url}. Start it first.")
            return

    for url in (SENDER, ATTACKER, RECEIVER):
        post(url + "/api/clear")

    # 1. Attacker only watches
    setup(sign=True, secure=True, mode="forward")
    post(SENDER + "/api/send", {"message": GENUINE})
    check("1. Normal message (attacker only watches)", last_received()["status"], "VALID")

    # 2. Auto-modify attack with security ON
    setup(sign=True, secure=True, mode="auto")
    post(SENDER + "/api/send", {"message": GENUINE})
    check("2. Auto-modify attack, security ON", last_received()["status"], "TAMPERED")

    # 3. Manual: modify + forge with attacker's key
    setup(sign=True, secure=True, mode="manual")
    post(SENDER + "/api/send", {"message": GENUINE})
    r = post(ATTACKER + "/api/action", {"id": first_pending_id(), "action": "forge", "new_message": FAKE})
    check("3. Manual attack: forged signature", r["status"], "TAMPERED")

    # 4. Manual: modify + remove signature
    post(SENDER + "/api/send", {"message": GENUINE})
    r = post(ATTACKER + "/api/action", {"id": first_pending_id(), "action": "strip", "new_message": FAKE})
    check("4. Manual attack: signature removed", r["status"], "NO_SIGNATURE")

    # 5. Replay the genuine packet from test 1 (oldest captured)
    oldest_id = get(ATTACKER + "/api/state")["captured"][-1]["id"]
    r = post(ATTACKER + "/api/replay", {"id": oldest_id})
    check("5. Replay attack (old genuine message)", r["status"], "REPLAY")

    # 6. Security OFF everywhere -> attack succeeds
    setup(sign=False, secure=False, mode="auto")
    post(SENDER + "/api/send", {"message": GENUINE})
    got = last_received()
    check("6. Security OFF: attack is NOT detected", got["status"], "UNVERIFIED",
          note=f"Priya received: \"{got['message']}\"  <-- changed by attacker!")

    # Restore safe defaults for the demo
    setup(sign=True, secure=True, mode="manual")

    print("=" * 64)
    print(f"  RESULT: {passed}/{total} tests passed")
    print("=" * 64)


if __name__ == "__main__":
    main()