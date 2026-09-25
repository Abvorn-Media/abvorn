import shutil
import tempfile
from pathlib import Path

import pytest

from abvorn.domination.orchestrator import DominationOrchestrator


@pytest.fixture
def learn_db(tmp_path):
    yield str(tmp_path / "learn.db")
    for p in sorted(tmp_path.glob("*"), reverse=True):
        try:
            p.unlink()
        except OSError:
            pass


class _FakeIntel:
    def __init__(self, entries):
        self._entries = entries

    def parse(self):
        return self._entries


class _FakePublisher:
    """Publish nothing; the test only cares about target selection."""

    def __init__(self):
        self.last_media_by_platform = None

    def publish_all(self, publish_targets, niche, media_paths=None, media_by_platform=None):
        self.last_media_by_platform = media_by_platform
        return [{"status": "posted", "platform": p} for p in publish_targets]


def _make_orchestrator(entries, db_path):
    orch = DominationOrchestrator()
    orch.content_intel = _FakeIntel(entries)
    orch.publisher = _FakePublisher()
    orch.pexels = _NoopAssets()
    orch.cinematic = _NoopCinematic()
    orch.audio = _NoopAudio()
    orch.learner = _NoopLearner(db_path)
    return orch


class _NoopAssets:
    def asset_for_niche(self, niche, count=1):
        return []


class _NoopCinematic:
    def apply_brand_overlay(self, *a, **k):
        return None


class _NoopAudio:
    def generate_voiceover_script(self, *a, **k):
        pass

    def count_assets(self):
        return 0


class _NoopLearner:
    def __init__(self, db_path):
        from abvorn.domination.self_learning_engine import SelfLearningEngine
        self._sle = SelfLearningEngine(db_path=db_path)

    def posted_urls(self):
        return self._sle.posted_urls()

    def niche_post_times(self):
        return self._sle.niche_post_times()

    def record_hook_test(self, *a, **k):
        return 1

    def record_post_performance(self, url, niche, platform, source_url="", **k):
        self._sle.record_post_performance(
            url=url, niche=niche, platform=platform, source_url=source_url
        )

    def record_posting_time(self, *a, **k):
        pass


def _entries():
    return [
        {
            "title": "Top Laptops",
            "niche": "laptops",
            "url": "https://abvorn.com/reviews/laptops/",
            "virality_score": 90,
            "sentiment": "positive",
        },
        {
            "title": "Top Mice",
            "niche": "mice",
            "url": "https://abvorn.com/reviews/mice/",
            "virality_score": 80,
            "sentiment": "positive",
        },
        {
            "title": "Top Keyboards",
            "niche": "keyboards",
            "url": "https://abvorn.com/reviews/keyboards/",
            "virality_score": 70,
            "sentiment": "positive",
        },
    ]


def test_cycle_builds_media_for_all_image_platforms(learn_db, tmp_path, monkeypatch):
    """When products resolve, real product-photo media must be composed for every
    image-capable platform in the run (not just Instagram), each at its own size."""
    from abvorn.domination import instagram_cards as igc
    from abvorn.domination import product_assets as pa
    from PIL import Image

    src = tmp_path / "src.jpg"
    Image.new("RGB", (1200, 1200), (30, 60, 200)).save(src)
    monkeypatch.setattr(igc, "_download_image", lambda p: str(src))

    def _fake_products(slug):
        return [{
            "name": "Dell XPS 13",
            "price": "$1,099",
            "role": "Overall Winner",
            "index": 0,
            "image": "https://example.invalid/xps.jpg",
        }]

    monkeypatch.setattr(pa, "load_products_for_niche", _fake_products)

    orch = _make_orchestrator(_entries(), learn_db)
    orch.publisher = _FakePublisher()

    result = orch.run_cycle(platforms=["instagram", "telegram", "linkedin", "x", "pinterest"])
    media_by_platform = orch.publisher.last_media_by_platform
    assert media_by_platform, "publisher got no per-platform media"
    assert "instagram" in media_by_platform and media_by_platform["instagram"]
    assert "telegram" in media_by_platform and media_by_platform["telegram"]
    assert "linkedin" in media_by_platform and media_by_platform["linkedin"]
    assert "x" in media_by_platform and media_by_platform["x"]
    assert "pinterest" in media_by_platform and media_by_platform["pinterest"]

    sizes = {p: Image.open(media_by_platform[p][0]).size for p in media_by_platform}
    assert sizes["linkedin"] == (1200, 627)
    assert sizes["x"] == (1200, 675)
    assert sizes["pinterest"] == (1000, 1500)
    assert sizes["instagram"] == (1080, 1350)
    assert sizes["telegram"] == (1080, 1350)
    assert result["steps"]["assets"]["source"] == "review_product_photos"


def test_cycle_picks_top_unposted_entry_on_second_run(learn_db):
    orch = _make_orchestrator(_entries(), learn_db)
    first = orch.run_cycle()
    assert first["title"] == "Top Laptops"
    second = orch.run_cycle()
    assert second["title"] == "Top Mice"
    third = orch.run_cycle()
    assert third["title"] == "Top Keyboards"


def test_cycle_with_niche_skips_posted_entries_in_niche(learn_db):
    entries = _entries()
    orch = _make_orchestrator(entries, learn_db)
    first = orch.run_cycle(niche="laptops")
    assert first["title"] == "Top Laptops"
    # second run in same niche: laptops already posted -> fall back to any laptops entry
    second = orch.run_cycle(niche="laptops")
    assert second["title"] == "Top Laptops"


def test_cycle_all_posted_falls_back_to_first_entry(learn_db):
    orch = _make_orchestrator(_entries(), learn_db)
    orch.run_cycle()
    orch.run_cycle()
    orch.run_cycle()
    # all three posted -> next run rotates to the least-recently-posted niche,
    # which is the first one posted (laptops), not blindly entries[0] forever.
    fourth = orch.run_cycle()
    assert fourth["title"] == "Top Laptops"


def test_cycle_shares_canonical_niche_url_not_stale_dated_article(learn_db, monkeypatch):
    """The social link must point at the canonical /reviews/<niche>/ hub — never
    the stale dated flat file pulled from the RSS feed — so shared links look
    like the proper niche page."""
    from abvorn.domination import product_assets as pa
    monkeypatch.setattr(pa, "load_products_for_niche", lambda slug: [])

    entries = [{
        "title": "Best Gaming Mice 2026: Logitech vs Razer Compared",
        "niche": "webcams",
        "url": "https://abvorn.com/reviews/gaming-mice/best-gaming-mice-2026-logitech-vs-razer-compared-2026-08-17.html",
        "virality_score": 90,
        "sentiment": "positive",
    }]
    orch = _make_orchestrator(entries, learn_db)

    captured = {}

    class _CapPub:
        def publish_all(self, publish_targets, niche, media_paths=None, media_by_platform=None):
            captured.update(publish_targets)
            return [{"status": "posted", "platform": p} for p in publish_targets]

    orch.publisher = _CapPub()
    orch.run_cycle(platforms=["x"])

    thread = captured["x"]
    assert thread[-1] == "Full breakdown: https://abvorn.com/reviews/gaming-mice/"
    # shared link is the canonical hub; the dedupe key is the source article,
    # date-normalized so a reprint of the same article cannot re-post
    assert orch.learner.posted_urls() == {
        "https://abvorn.com/reviews/gaming-mice/best-gaming-mice-2026-logitech-vs-razer-compared.html"
    }


def test_cycle_deduplicates_by_canonical_hub_across_cycle_runs(learn_db, monkeypatch):
    """After one cycle posts a niche hub, a second cycle must skip it (the
    posted set now contains the canonical URL) and pick the next niche."""
    from abvorn.domination import product_assets as pa
    monkeypatch.setattr(pa, "load_products_for_niche", lambda slug: [])

    entries = _entries()
    orch = _make_orchestrator(entries, learn_db)
    first = orch.run_cycle()
    second = orch.run_cycle()
    assert first["title"] != second["title"]
    # both recorded canonical URLs for their niches
    urls = orch.learner.posted_urls()
    assert "https://abvorn.com/reviews/laptops/" in urls
    assert "https://abvorn.com/reviews/mice/" in urls


def test_cycle_deduplicates_by_article_not_niche_hub(learn_db, monkeypatch):
    """Two articles in the SAME niche are two distinct posts.

    Dedupe used to key on the shared niche hub, so a niche with many reviews
    collapsed to a single post and the cycle then re-posted the top-scoring
    niche forever. Dedupe must key on each article's own URL.
    """
    from abvorn.domination import product_assets as pa
    monkeypatch.setattr(pa, "load_products_for_niche", lambda slug: [])

    entries = [
        {
            "title": "Best Laptops A",
            "niche": "laptops",
            "url": "https://abvorn.com/reviews/laptops/best-laptops-a.html",
            "virality_score": 90,
            "sentiment": "positive",
        },
        {
            "title": "Best Laptops B",
            "niche": "laptops",
            "url": "https://abvorn.com/reviews/laptops/best-laptops-b.html",
            "virality_score": 80,
            "sentiment": "positive",
        },
    ]
    orch = _make_orchestrator(entries, learn_db)

    first = orch.run_cycle()
    second = orch.run_cycle()

    # same niche, different article — not a repeat
    assert first["title"] == "Best Laptops A"
    assert second["title"] == "Best Laptops B"
    assert second["niche"] == "laptops"
    assert orch.learner.posted_urls() == {
        "https://abvorn.com/reviews/laptops/best-laptops-a.html",
        "https://abvorn.com/reviews/laptops/best-laptops-b.html",
    }


def test_cycle_skips_dated_republication_of_posted_article(learn_db, monkeypatch):
    """The live feed republishes one article under a new dated filename.

    ...-compared-2026-08-24.html and ...-compared-2026-08-31.html are the same
    content, so posting both would put the same article up twice in a row.
    """
    from abvorn.domination import product_assets as pa
    monkeypatch.setattr(pa, "load_products_for_niche", lambda slug: [])

    base = "https://abvorn.com/reviews/4k-monitors/best-4k-monitors-compared"
    entries = [
        {
            "title": "Best 4k-Monitors Compared (Aug 24)",
            "niche": "4k-monitors",
            "url": f"{base}-2026-08-24.html",
            "virality_score": 90,
            "sentiment": "positive",
        },
        {
            "title": "Best 4k-Monitors Compared (Aug 31 reprint)",
            "niche": "4k-monitors",
            "url": f"{base}-2026-08-31.html",
            "virality_score": 85,
            "sentiment": "positive",
        },
        {
            "title": "Top Mice",
            "niche": "mice",
            "url": "https://abvorn.com/reviews/mice/",
            "virality_score": 80,
            "sentiment": "positive",
        },
    ]
    orch = _make_orchestrator(entries, learn_db)

    first = orch.run_cycle()
    second = orch.run_cycle()

    assert first["title"] == "Best 4k-Monitors Compared (Aug 24)"
    # the dated reprint is suppressed; the next post is different content
    assert second["title"] == "Top Mice"
    assert orch.learner.posted_urls() == {
        f"{base}.html",
        "https://abvorn.com/reviews/mice/",
    }


def test_cycle_prefers_different_niche_over_feed_order(learn_db, monkeypatch):
    """Feed order must not make the engine post one niche twice in a row.

    With two unposted laptops articles and one unposted mice article, walking
    the feed in order would post laptops, laptops, mice. Diversity is a
    preference, not a constraint: the second laptops article is still used once
    mice is spent.
    """
    from abvorn.domination import product_assets as pa
    monkeypatch.setattr(pa, "load_products_for_niche", lambda slug: [])

    entries = [
        {
            "title": "Laptops A",
            "niche": "laptops",
            "url": "https://abvorn.com/reviews/laptops/a.html",
            "virality_score": 90,
            "sentiment": "positive",
        },
        {
            "title": "Laptops B",
            "niche": "laptops",
            "url": "https://abvorn.com/reviews/laptops/b.html",
            "virality_score": 85,
            "sentiment": "positive",
        },
        {
            "title": "Mice",
            "niche": "mice",
            "url": "https://abvorn.com/reviews/mice/m.html",
            "virality_score": 80,
            "sentiment": "positive",
        },
    ]
    orch = _make_orchestrator(entries, learn_db)

    titles = [orch.run_cycle()["title"] for _ in range(3)]
    assert titles == ["Laptops A", "Mice", "Laptops B"]
    # every article still used exactly once
    assert len(orch.learner.posted_urls()) == 3


def test_cycle_rotates_to_least_recently_posted_niche(learn_db, monkeypatch):
    """Once every article is spent, rotate to the least-recently-posted niche.

    The old fallback returned entries[0] unconditionally, so the top-scoring
    niche (laptops) was re-posted on every single cycle.
    """
    from abvorn.domination import product_assets as pa
    monkeypatch.setattr(pa, "load_products_for_niche", lambda slug: [])

    entries = [
        {
            "title": "Top Keyboards",
            "niche": "keyboards",
            "url": "https://abvorn.com/reviews/keyboards/",
            "virality_score": 70,
            "sentiment": "positive",
        },
        {
            "title": "Top Mice",
            "niche": "mice",
            "url": "https://abvorn.com/reviews/mice/",
            "virality_score": 80,
            "sentiment": "positive",
        },
        {
            "title": "Top Laptops",
            "niche": "laptops",
            "url": "https://abvorn.com/reviews/laptops/",
            "virality_score": 90,
            "sentiment": "positive",
        },
    ]
    orch = _make_orchestrator(entries, learn_db)

    # Post keyboards FIRST so it is the least recently posted, then drain the rest.
    orch.run_cycle(niche="keyboards")
    orch.run_cycle()  # laptops (highest virality, unposted)
    orch.run_cycle()  # mice

    # Everything is posted. Rotation must go back to keyboards, NOT laptops.
    rotated = orch.run_cycle()
    assert rotated["title"] == "Top Keyboards"


def test_cycle_never_posts_same_article_twice_in_a_row(learn_db, monkeypatch):
    """The reported symptom: the same niche posted over and over."""
    from abvorn.domination import product_assets as pa
    monkeypatch.setattr(pa, "load_products_for_niche", lambda slug: [])

    entries = [
        {
            "title": "Top Laptops",
            "niche": "laptops",
            "url": "https://abvorn.com/reviews/laptops/",
            "virality_score": 90,
            "sentiment": "positive",
        },
        {
            "title": "Top Mice",
            "niche": "mice",
            "url": "https://abvorn.com/reviews/mice/",
            "virality_score": 80,
            "sentiment": "positive",
        },
    ]
    orch = _make_orchestrator(entries, learn_db)

    titles = [orch.run_cycle()["title"] for _ in range(6)]
    # both niches get a turn, then rotation alternates between them even though
    # re-posting inserts no new dedupe row
    assert titles[:2] == ["Top Laptops", "Top Mice"]
    assert titles[2:] == ["Top Laptops", "Top Mice", "Top Laptops", "Top Mice"]