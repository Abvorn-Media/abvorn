import argparse
import json
import re
import sys

import requests

REPO = "Abvorn-Media/abvorn"
CANARY_REF = "origin/main"
CANARY_FILENAME = "docs/reviews/tv/index.html"

# The product signal is a real Amazon ASIN, not an affiliate link shape. Pages
# legitimately render several link forms (https://www.amazon.com/dp/B0...,
# a.co/dp/..., a bare ?tag=... search URL), so counting "/dp/" reported 0 for
# every page on the site and the canary could never pass. An ASIN is the thing
# that actually makes a product buyable and attributable, so count those.
REGEX_ASIN = re.compile(r"\bB0[A-Z0-9]{8}\b")
REGEX_DP = re.compile(r"/dp/")
# Mojibake is double-encoded UTF-8 (e.g. an em dash read as cp1252) and can also
# survive as U+FFFD after a lossy decode, which is how it reaches disk on
# Windows. Both shapes are corruption.
REGEX_MOJI = re.compile("\u00e2\u20ac|\u00c3\u00a9|\u00c3\u00a2|\u00c3\u0083|\u00c3\\. |\ufffd")
REGEX_IMG = re.compile(r"<img[^>]+src=[\"'](?:https?:)?//[^\"']+media-amazon\.com")
# Generated stub product ("Top tv Pick") — the fingerprint of a failed research
# run that was published anyway.
REGEX_PLACEHOLDER = re.compile(r"Top\s+[\w][\w\s\-&]*?\s+Pick")


def live_blob(retries: int = 3, timeout: int = 20) -> str:
    """Fetch the live published page from GitHub (read-only, no deploy).

    Raises requests.RequestException when the page cannot be fetched. Callers
    must NOT treat that as a pass: raw.githubusercontent.com resets connections
    often enough that a swallowed timeout once turned a genuinely broken hub
    into a green canary run.
    """
    import time

    url = f"https://raw.githubusercontent.com/{REPO}/main/{CANARY_FILENAME}"
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            # Decode as UTF-8 explicitly: without it requests guesses latin-1 and
            # every em dash reads as mojibake, which would fail the check on an
            # otherwise healthy page.
            return r.content.decode("utf-8", errors="replace")
        except requests.RequestException as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    raise last  # type: ignore[misc]


def count(haystack: str) -> dict[str, int]:
    return {
        "asins": len(set(REGEX_ASIN.findall(haystack))),
        "dp_links": len(REGEX_DP.findall(haystack)),
        "imgs": len(REGEX_IMG.findall(haystack)),
        "mojibake": len(REGEX_MOJI.findall(haystack)),
        "placeholders": len(REGEX_PLACEHOLDER.findall(haystack)),
        "len": len(haystack),
    }


def verdict(stats: dict[str, int]) -> bool:
    """A hub is healthy when it sells something real and is not corrupted.

    Placeholder products are fatal even alongside real ones: a "Top <niche>
    Pick" stub carries invented scores and a tag-only search link, so a page
    carrying one is shipping a product that cannot be bought.
    """
    return (
        int(stats.get("asins", 0)) > 0
        and int(stats.get("mojibake", 0)) == 0
        and int(stats.get("placeholders", 0)) == 0
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Commit-watch canary for the tv review hub")
    p.add_argument("--min-asins", type=int, default=1)
    p.add_argument("--min-imgs", type=int, default=1)
    args = p.parse_args()

    blob = live_blob()
    c = count(blob)
    # verdict() owns the product+encoding contract; the image floor stays here
    # because a hub can legitimately render without hero art.
    healthy = verdict(c) and c["asins"] >= args.min_asins and c["imgs"] >= args.min_imgs
    print(json.dumps({
        "health": "HEALTHY" if healthy else "REGRESSED",
        "placeholders_are_fatal": c["placeholders"] > 0,
        **c,
    }, indent=2))
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
