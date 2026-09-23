import argparse
import json
import re
import subprocess
import sys
from typing import Any

import requests

REPO = "Abvorn-Media/abvorn"
CANARY_REF = "origin/main"
CANARY_FILENAME = "docs/reviews/tv/index.html"

REGEX_DP = re.compile(r"/dp/")
REGEX_MOJI = re.compile(r"â€|Ã©|Ã¢|Ãƒ|Ã\. ")


def live_blob() -> str:
    """Fetch the live published page from GitHub API (read-only, no deploy)."""
    url = f"https://raw.githubusercontent.com/{REPO}/origin/main/{CANARY_FILENAME}"
    # NB: raw.githubusercontent.com uses ref/branch, not 'origin/main'. Use the
    # git ref name that resolves: default branch is a plain branch name.
    url = url.replace("/origin/main/", "/main/")
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.text


def count(haystack: str) -> dict[str, int]:
    return {
        "asins": len(REGEX_DP.findall(haystack)),
        "mojibake": len(REGEX_MOJI.findall(haystack)),
        "len": len(haystack),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Commit-watch canary for the tv review hub")
    p.add_argument("--min-asins", type=int, default=1)
    args = p.parse_args()

    blob = live_blob()
    c = count(blob)
    healthy = c["asins"] >= args.min_asins and c["mojibake"] == 0
    print(json.dumps({"health": "HEALTHY" if healthy else "REGRESSED", **c}, indent=2))
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
