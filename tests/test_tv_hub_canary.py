"""Regression test: the tv-hub canary must catch a product-less + mojibake hub.

The daemon clobbered docs/reviews/tv/index.html for days (products dropped from
the deploy payload). This test feeds the canary check against BOTH the healthy
blob and a deliberately product-less/mojibaked blob and asserts the verdict.

The canary also has to recognise the placeholder fingerprint, because a failed
research run used to publish a "Top <niche> Pick" stub that scored 6.7/10 and
linked to a bare ?tag=... search URL instead of a product.

The *live* check is opt-in (ABVORN_LIVE_CANARY=1). It asserts against the
published site, which no code commit can change, so leaving it in the default
suite makes CI permanently red for the tv hub's real, still-open content bug
instead of for the code under test. Production state is monitored by
scripts/watch_tv_hub.py; the mechanics are pinned by the tests below.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

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
    n_m = canary.count(
        REGRESSED_PAGE.format('"products":[]')
        # Inject the corruption the canary must catch. The target has to
        # match the fixture verbatim: it reads "Television hubs." with no
        # comma, so the previous "Television, hubs." needle never matched
        # and this test asserted against an uncorrupted blob.
        .replace("Television hubs.", "Televis\ufffdon hubs.")
    )
    assert n_m["mojibake"] > 0


def test_canary_verdict_healthy():
    assert canary.verdict({"asins": 2, "mojibake": 0})
    assert not canary.verdict({"asins": 0, "mojibake": 0})
    assert not canary.verdict({"asins": 2, "mojibake": 1})
    # A stub alongside real products still fails: the stub is unbuyable and
    # carries invented scores.
    assert not canary.verdict({"asins": 2, "mojibake": 0, "placeholders": 1})
    assert canary.verdict({"asins": 2, "mojibake": 0, "placeholders": 0})


def test_canary_flags_a_placeholder_product_page():
    """The shape the tv hub actually shipped: one invented product, no ASIN, a
    tag-only link. The canary must report the placeholder, and the verdict must
    refuse the page even though the blob is long and un-corrupted."""
    stub = """<!doctype html>
<html><head><script id="abvorn-rps-data" type="application/json">
{"products": [{"name": "Top tv Pick", "price": "Check Price",
  "scores": {"Quality": 7.0, "Features": 7.4}, "overall": 6.7,
  "label": "Solid", "url": "?tag=viraltestco-20"}], "niche": "tv"}
</script></head><body>
""" + ("<p>Choosing the right TV in 2026 can feel overwhelming.</p>" * 200) + """
</body></html>"""
    n = canary.count(stub)
    assert n["asins"] == 0
    assert n["mojibake"] == 0
    assert n["placeholders"] >= 1
    assert canary.verdict(n) is False


@pytest.mark.skipif(
    os.environ.get("ABVORN_LIVE_CANARY") != "1",
    reason="live published-site check; set ABVORN_LIVE_CANARY=1 to run",
)
def test_live_origin_main_is_healthy():
    import requests
    try:
        live = canary.live_blob()
    except requests.RequestException as e:
        # Skip, never pass. An earlier version returned here on any exception,
        # so a 20s network timeout reported a green canary for a hub that was
        # still carrying one fabricated product.
        pytest.skip(f"cannot reach GitHub raw: {e}")
    n = canary.count(live)
    assert n["asins"] >= 1, f"live tv hub has no products: {n}"
    assert n["mojibake"] == 0, f"live tv hub has mojibake: {n}"
    assert n["placeholders"] == 0, f"live tv hub has placeholder products: {n}"
