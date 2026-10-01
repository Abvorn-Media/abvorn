"""post_title must be about the niche it is filed under.

`post_title` is raw LLM output and it reaches the filesystem through
`_title_slug()` -> `fname` -> `docs/reviews/<niche>/<fname>.html`.
`_title_slug` slugifies whatever it is handed, so an off-topic title becomes a
legitimate-looking filename inside a real niche directory, self-canonical and
open to search engines. That is how these shipped under a real niche:

  reviews/laptops/first-time-hotel-booking-guide-...
  reviews/laptops/solar-panels-buying-guide-for-first-time-buyers.html
  reviews/laptops/coffee-grinder-buying-guide-for-first-time-buyers-...

Nothing between the model and the disk asked whether the title was on-topic, so
the defect recurred for a month across three separate niches. The quality
scorer rated all of them 10.0, so it did not catch them either.

`niche_relevance()` is the missing gate: a title's content words must overlap
the niche slug or the names of the products in the article. The article's own
products supply the vocabulary, so there is no curated word list to drift.
"""

import pytest

from src.deployment import niche_relevance, scan_published_reviews

# (niche, title, products) -- the titles that actually shipped.
OFF_TOPIC = [
    ("laptops", "First-Time Hotel Booking Guide: Avoid Costly Mistakes & Book Right", []),
    ("laptops", "Solar Panels Buying Guide for First-Time Buyers", []),
    ("laptops",
     "Coffee Grinder Buying Guide for First-Time Buyers: Get It Right & Save", []),
    ("robot-vacuums", "First-Time Hotel Booking Guide: Save Money & Avoid Mistakes", []),
    # Off-topic with products present: the guard must still fire, because the
    # product names are laptop/TV words and share nothing with the title.
    ("laptops", "Spa Reservation Scheduling Guide for Massage Therapists",
     [{"name": "Lenovo ThinkPad X1 Carbon", "asin": "B0C1TEST"}]),
    ("webcams", "Choosing a Mortgage Lender: First-Time Homebuyer Guide",
     [{"name": "Logitech Brio 4K", "asin": "B0C2TEST"}]),
]

# Titles that must survive: on-topic, plus the near-miss shapes that a naive
# keyword check would wrongly kill.
ON_TOPIC = [
    ("laptops", "The Ultimate Laptop Buying Guide: Lenovo, HP, and Jumper Compared",
     [{"name": "Lenovo ThinkPad X1 Carbon"}]),
    ("laptops", "The Ultimate 2026 Guide to Choosing the Best 15.6-Inch Laptop: Lenovo, HP",
     [{"name": "HP EliteBook 840"}]),
    # "smart"/"home" are the entire topic of this niche -- if the stopword list
    # treats them as generic, this page and 4 siblings get wrongly rejected.
    ("smart-home", "Best Smart Home Devices 2026: Top Picks & Buying Guide",
     [{"name": "Echo Show 5"}]),
    ("smart-home", "Transform Your Space: The Complete Smart Home Buying Guide",
     [{"name": "Nest Thermostat"}]),
    # The one that needs stemming: title says "webcam", niche says "webcams".
    ("webcams", "The Ultimate Webcam Buying Guide: Find the Perfect Camera for Streaming",
     [{"name": "Logitech C920"}]),
    ("robot-vacuums", "Best Robot Vacuums 2026 - Comparison Buying Guide",
     [{"name": "Roborock Q7 Max"}]),
    # Matches only via the product name, not the slug.
    ("tv", "Roku 40 Select Series TV Buying Guide for First-Time Buyers",
     [{"name": "Roku Express 4K"}]),
]


class TestOffTopicTitlesBlocked:
    @pytest.mark.parametrize("niche,title,products", OFF_TOPIC)
    def test_rejected(self, niche, title, products):
        assert niche_relevance(niche, title, products)["relevant"] is False

    def test_reason_is_actionable(self):
        """The caller logs this string, so it has to name the niche."""
        r = niche_relevance("laptops", "Solar Panels Buying Guide for First-Time Buyers", [])
        assert "laptops" in r["reason"]
        assert r["shared"] == []


class TestOnTopicTitlesKept:
    @pytest.mark.parametrize("niche,title,products", ON_TOPIC)
    def test_accepted(self, niche, title, products):
        assert niche_relevance(niche, title, products)["relevant"] is True


class TestDegenerateInput:
    def test_empty_title_is_not_a_failure(self):
        """Nothing to contradict -- must not manufacture a rejection."""
        assert niche_relevance("laptops", "", [])["relevant"] is True

    def test_stopword_only_title_is_not_a_failure(self):
        assert niche_relevance("laptops", "The Best Of The Best", [])["relevant"] is True

    def test_niche_without_comparable_vocabulary_does_not_block(self):
        """No vocabulary means no evidence of off-topic, not proof of it.

        A slug always yields tokens ('brand-new-niche' -> brand, new, niche),
        so the empty-vocabulary branch only fires when the slug is itself
        entirely stopwords *and* no product names were supplied.
        """
        r = niche_relevance("the-and-of", "Some Title Here", [])
        assert r["relevant"] is True
        assert r["checked"] == 0

    def test_slug_vocabulary_alone_is_enough_to_judge(self):
        """With no products, the slug words are all the evidence there is."""
        assert niche_relevance("laptops", "A Guide To Laptop Backpacks",
                               [])["relevant"] is True
        assert niche_relevance("laptops", "A Guide To Hotel Booking",
                               [])["relevant"] is False

    def test_string_products_are_accepted(self):
        """Products arrive as dicts from research, but tolerate bare names."""
        assert niche_relevance("laptops", "A MacBook Air Comparison",
                               ["MacBook Air M3"])["relevant"] is True

    def test_case_and_punctuation_are_ignored(self):
        r = niche_relevance("TV", "Best TV's: Roku & Sony!", [{"name": "Roku"}])
        assert r["relevant"] is True


class TestAgainstLiveCorpus:
    """Zero false positives across every review currently published.

    This is the assertion that makes the rule safe to enforce: a guard that
    blocks real reviews is worse than the bug it prevents.
    """

    def test_no_published_review_is_rejected(self):
        import json
        import re
        from pathlib import Path

        reviews = scan_published_reviews("docs")
        assert len(reviews) > 100, "corpus unexpectedly small; guard this test"

        rejected = []
        for r in reviews:
            path = Path("docs") / r["rel"].lstrip("/")
            products = []
            try:
                html = path.read_text(encoding="utf-8")
                m = re.search(r'id="abvorn-rps-data"[^>]*>(\{.*?\})</script>', html, re.S)
                if m:
                    data = json.loads(m.group(1))
                    prods = data.get("products") or []
                    if isinstance(prods, dict):
                        prods = list(prods.values())
                    products = [p for p in prods if isinstance(p, dict)]
            except Exception:
                pass
            if not niche_relevance(r["slug"], r["title"], products)["relevant"]:
                rejected.append((r["slug"], r["title"]))

        assert not rejected, f"{len(rejected)}/{len(reviews)} live reviews rejected: {rejected[:5]}"
