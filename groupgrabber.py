import os, time, csv, hashlib, hmac, base64, requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
API = "https://api.vrchat.cloud/api/1"
UA  = UA = "CynGroupScanner/0.1 cynderardman@gmail.com"
sess = requests.Session(); sess.headers["User-Agent"] = UA
def totp_now(secret):
    ts = int(time.time()) // 30
    key = base64.b32decode(secret, True)
    h   = hmac.new(key, ts.to_bytes(8, "big"), hashlib.sha1).digest()
    o   = h[19] & 15
    return str((int.from_bytes(h[o:o+4], "big") & 0x7fffffff) % 1_000_000).zfill(6)
def login():
    r = sess.get(f"{API}/auth/user", auth=HTTPBasicAuth(USER, PASS))
    if r.ok: return
    if "requiresTwoFactorAuth" not in r.text: raise RuntimeError(r.text)
    code = totp_now(TOTP) if TOTP else input("6‑digit TOTP: ")
    if not sess.post(f"{API}/auth/twofactorauth/totp/verify", json={"code": code}).ok:
        raise RuntimeError("2FA failed")
def main():
    login()
    rows = []
    for m in sess.get(f"{API}/groups/{GROUP}/members").json():
        uid, name = m["id"], m["displayName"]
        for g in sess.get(f"{API}/users/{uid}/groups").json():
            rows.append([uid, name, g["id"], g["name"]])
        time.sleep(0.8)      # stay under 500 req / 5 min
    with open("member_group_map.csv", "w", newline="", encoding="utf‑8") as f:
        csv.writer(f).writerows([["memberId","memberName","groupId","groupName"], *rows])
    print(f"Saved {len(rows)} lines ➜ member_group_map.csv")
if __name__ == "__main__":
    load_dotenv()
    USER, PASS, TOTP, GROUP = [os.getenv(k) for k in
        ("VRC_USER","VRC_PASS","VRC_TOTP","GROUP_ID")]
    main()
# ----- END SCRIPT -----
~

#!/usr/bin/env python3
# VRChat Group‑to‑Groups scraper
# Docs: https://vrchatapi.github.io
# Author: CynGroupScanner/0.2  –  contact: cyn@example.com

import os, time, csv, base64, hashlib, hmac, requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

API_BASE = "https://api.vrchat.cloud/api/1"
CHUNK    = 100          # members per page when paginating
MEM_SLEEP = 0.2         # pause between member‑list pages
USR_SLEEP = 0.8         # pause between /users/{id}/groups calls

###############################################################################
# Helper: minimal TOTP (works with VRChat’s 30‑second window)
###############################################################################
def totp_now(b32_secret: str) -> str:
    ts = int(time.time()) // 30
    key = base64.b32decode(b32_secret, True)
    h   = hmac.new(key, ts.to_bytes(8, "big"), hashlib.sha1).digest()
    o   = h[19] & 15
    return str((int.from_bytes(h[o:o+4], "big") & 0x7fffffff) % 1_000_000).zfill(6)

###############################################################################
# Session + login
###############################################################################
def login(sess: requests.Session, user: str, pw: str, totp_secret: str | None):
    """Perform basic‑auth login + optional TOTP verify."""
    r = sess.get(f"{API_BASE}/auth/user", auth=HTTPBasicAuth(user, pw))
    if r.status_code == 200:
        return                                  # success, no 2FA required

    data = r.json()
    if r.status_code == 401 and data.get("requiresTwoFactorAuth"):
        code = totp_now(totp_secret) if totp_secret else input("Enter 6‑digit TOTP: ")
        v = sess.post(f"{API_BASE}/auth/twofactorauth/totp/verify", json={"code": code})
        if v.status_code == 200:
            return
        raise RuntimeError(f"2FA failed → {v.text}")
    raise RuntimeError(f"Login failed → {r.text}")

###############################################################################
# Fetch all members, handling pagination + nice errors
###############################################################################
def fetch_all_members(sess: requests.Session, group_id: str) -> list[dict]:
    members, offset = [], 0
    while True:
        url = f"{API_BASE}/groups/{group_id}/members?offset={offset}&n={CHUNK}"
        page_raw = sess.get(url).json()

        # Handle errors returned as {"error":{...}}
        if isinstance(page_raw, dict) and "error" in page_raw:
            raise RuntimeError(f"Group call failed → {page_raw['error']['message']}")

        # When you supply n/offset, VRChat wraps the results:
        # { "totalCount": 123, "offset": 0, "members": [ ... ] }
        page = page_raw.get("members") if isinstance(page_raw, dict) else page_raw
        members.extend(page)

        if len(page) < CHUNK:                   # last page reached
            break
        offset += CHUNK
        time.sleep(MEM_SLEEP)                   # respect the API
    return members

###############################################################################
# Main orchestration
###############################################################################
def main():
    load_dotenv()
    USER   = os.getenv("VRC_USER")
    PASS   = os.getenv("VRC_PASS")
    TOTP   = os.getenv("VRC_TOTP") or None
    GROUP  = os.getenv("GROUP_ID")
    UA     = os.getenv("VRC_UA", "CynGroupScanner/0.2 cyn@example.com")
    if not all((USER, PASS, GROUP)):
        raise SystemExit("✖  VRC_USER, VRC_PASS, and GROUP_ID must be set in .env")

    sess = requests.Session()
    sess.headers["User-Agent"] = UA

    login(sess, USER, PASS, TOTP)
    print("✓  Logged in")

    members = fetch_all_members(sess, GROUP)
    print(f"✓  Pulled {len(members)} group members")

    rows = []
    for idx, m in enumerate(members, start=1):
        uid, name = m["id"], m["displayName"]
        groups = sess.get(f"{API_BASE}/users/{uid}/groups").json()
        # Users can hide group info – then we get [] or {} – handle both
        if isinstance(groups, dict) and "error" in groups:
            groups = []      # privacy‑hidden
        for g in groups:
            rows.append([uid, name, g["id"], g["name"]])
        if idx % 50 == 0:
            print(f"  …processed {idx}/{len(members)} members")
        time.sleep(USR_SLEEP)

    if not rows:
        print("⚠  No group links collected (all members hide groups?)")
    else:
        with open("member_group_map.csv", "w", newline="", encoding="utf‑8") as f:
            csv.writer(f).writerows(
                [["memberId", "memberName", "groupId", "groupName"], *rows]
            )
        print(f"✓  Saved {len(rows)} lines → member_group_map.csv")

if __name__ == "__main__":
    main()
