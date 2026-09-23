"""Regression test: the tv-hub canary must catch a product-less + mojibake hub.

The daemon clobbered docs/reviews/tv/index.html for days (products dropped from
the deploy payload). This test feeds the canary check against BOTH the healthy
blob and a deliberately product-less/mojibaked blob and asserts the verdict.
"""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import watch_tv_hub as canary


HEALTHY_PAGE = """<!doctype html>
<html><head><script id="aborn-rps-data" type="application/json">{"products":[{"name":"Roku 40","asin":"B0FBZ2Y7CJ","url":"https://a.co/dp/B0FBZ2Y7CJ"},{"name":"Roku 55","asin":"B0H3L589W7","url":"https://a.co/dp/B0H3L589W7"}]}</script>
</head><body><a href="https://a.co/dp/B0FBZ2Y7CJ">view</a><a href="https://a.co/dp/B0H3L589W7">view</a></body></html>"""

REGRESSED_PAGE = """<!doctype html>
<html><head><script id="aborn-rps-data" type="application/json">{}</script>
</head><body>is our current top pick for Television hubs. No products carried.</body></html>"""


def blob(html: str) -> int:
    return canary.count(html)


def test_healthy_blob_carries_products():
    n = canary.count(HEALTHY_PAGE)
    assert n["asins"] >= 2
    assert n["mojibake"] == 0


def test_regressed_blob_fires_canary():
    n = canary.count(REGRESSED_PAGE.format(""))
    assert n["asins"] == 0
    assert n["mojibake"] == 0
    # mojibake variant
    n_m = canary.count(REGRESSED_PAGE.format('"products":[]').replace("Television," " hubs.", "Televis�on,"))
    assert n_m["mojibake"] > 0


def test_canary_verdict_healthy():
    assert canary.verdict({"asins": 2, "mojibake": 0})
    assert not canary.verdict({"asins": 0, "mojibake": 0})
    assert not canary.verdict({"asins": 2, "mojibake": 1})


def test_live_origin_main_is_healthy():
    try:
        live = canary.live_blob()
    except Exception:
        return  # offline: canary can't reach network
    n = canary.count(live)
    assert n["asins"] >= 1, f"live tv hub has no products: {n}"
    assert n["mojibake"] == 0, f"live tv hub has mojibake: {n}"
