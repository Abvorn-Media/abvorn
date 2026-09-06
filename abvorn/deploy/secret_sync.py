#!/usr/bin/env python3
import base64, json
from pathlib import Path
import requests
from nacl import encoding, public

env = {}
for line in Path("/opt/abvorn-core/.env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        env[k] = v.strip()

tok = env.get("GITHUB_TOKEN", "")
repo = env.get("GITHUB_REPO", "Abvorn-Media/abvorn")
owner, name = repo.split("/")

H = {
    "Authorization": f"Bearer {tok}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "abvorn-deploy",
}
BASE = f"https://api.github.com/repos/{owner}/{name}/actions/secrets"

def set_secret(sname, value):
    r = requests.get(f"{BASE}/public-key", headers=H)
    r.raise_for_status()
    pk = r.json()
    box = public.SealedBox(public.PublicKey(pk["key"], encoding.Base64Encoder()))
    enc = base64.b64encode(box.encrypt(value.encode())).decode()
    r = requests.put(f"{BASE}/{sname}", headers=H,
                     json={"encrypted_value": enc, "key_id": pk["key_id"]})
    print(f"upserted {sname} -> HTTP {r.status_code}")

try:
    r = requests.get(BASE, headers=H)
    r.raise_for_status()
    names = [s["name"] for s in r.json().get("secrets", [])]
    print("existing secrets:", sorted(names), "total:", r.json().get("total_count"))
except Exception as e:
    print("list failed:", e)

set_secret("AMAZON_TAG", "viraltestco-20")

sf = Path.home() / ".abvorn/boardroom/secrets.json"
if sf.exists():
    try:
        creds = json.loads(sf.read_text(encoding="utf-8")).get("GA4_CREDENTIALS_JSON", "")
        if creds:
            set_secret("GA4_CREDENTIALS_JSON", json.dumps(json.loads(creds), separators=(",", ":")))
            print("GA4_CREDENTIALS_JSON repaired, len", len(creds))
    except Exception as e:
        print("ga4 cred repair skipped:", e)

print("done")