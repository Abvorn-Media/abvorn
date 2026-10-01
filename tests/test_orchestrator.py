import pytest, tempfile
from pathlib import Path
from unittest.mock import MagicMock
from abvorn.orchestrator.scheduler import Scheduler
from abvorn.agents.orchestrator import SiteDeployer


def _deployer():
    d = MagicMock()
    d.deploy_html.return_value = {"status": "success"}
    return d


def test_deploy_root_index_skips_when_empty_state():
    """With no niches or posts the daemon must not deploy a 'coming soon' homepage."""
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    assert sd.deploy_root_index(niches=[], posts=[]) is False
    deployer.deploy_html.assert_not_called()


def test_reviews_gates_phantom_post_cards():
    """A state post whose article page does not exist in the published remote
    tree (e.g. a stale 'coffee-grinder' row that 404s live) must not fabricate
    a homepage card. Real pages that exist must still be emitted."""
    class ExistenceDeployer:
        def __init__(self):
            self.existing = {
                "reviews/tv/index.html",
                "reviews/laptops/kindle-scribe.html",
            }
        def file_exists(self, rel):
            return rel.lstrip("/") in self.existing

    sd = SiteDeployer(ExistenceDeployer(), None)
    posts = [
        {"niche_slug": "tv", "title": "Budget 55-inch TV Guide",
         "filename": "index.html", "quality_score": 8.5},
        {"niche_slug": "laptops", "title": "Coffee Grinder Buying Guide",
         "filename": "coffee-grinder.html", "quality_score": 10.0},
        {"niche_slug": "laptops", "title": "Kindle Scribe Review",
         "filename": "kindle-scribe.html", "quality_score": 9.0},
    ]
    reviews = sd._reviews(["tv", "laptops"], posts)
    titles = [r["title"] for r in reviews]
    assert "Coffee Grinder Buying Guide" not in titles, "phantom post card must be dropped"
    assert "Kindle Scribe Review" in titles, "real review card must be kept"
    assert "Budget 55-inch TV Guide" in titles, "existing index card must be kept"


def test_reviews_skips_posts_with_no_article_page():
    """A state post with an empty filename, or an explicitly unpublished
    status, must not produce a card.

    Regression: the robot-vacuum 'hotel booking' rows had their filename
    cleared when their pages were deleted. The old code only ran the
    file_exists gate `if filename and ...`, so an empty filename skipped the
    gate entirely and still emitted a card - pointing at the niche hub while
    keeping the stale 'First-Time Hotel Booking' title. That is what kept the
    hotel cards on the live homepage and the niche landing page.
    """
    class EverythingExists:
        def file_exists(self, rel):
            return True

    sd = SiteDeployer(EverythingExists(), None)
    posts = [
        # soft-unpublished: page deleted, filename cleared
        {"niche_slug": "robot-vacuums",
         "title": "First-Time Hotel Booking Guide",
         "filename": "", "deployment_status": "unpublished",
         "quality_score": 10.0},
        # no filename at all, still "pending"
        {"niche_slug": "robot-vacuums",
         "title": "Another Draft Row", "filename": "",
         "deployment_status": "pending", "quality_score": 9.0},
        # explicitly removed
        {"niche_slug": "robot-vacuums",
         "title": "Deleted Robot Guide", "filename": "gone.html",
         "deployment_status": "deleted", "quality_score": 9.0},
        # the real guide: published, page exists -> must survive
        {"niche_slug": "robot-vacuums",
         "title": "Best Robot Vacuums 2026",
         "filename": "best-robot-vacuums-2026.html",
         "deployment_status": "deployed", "quality_score": 8.0},
    ]
    reviews = sd._reviews(["robot-vacuums"], posts)
    titles = [r["title"] for r in reviews]
    for dropped in ("First-Time Hotel Booking Guide", "Another Draft Row",
                    "Deleted Robot Guide"):
        assert dropped not in titles, f"{dropped!r} must not render a card"
    assert "Best Robot Vacuums 2026" in titles, "the real published guide must render"
    card = next(r for r in reviews if r["title"] == "Best Robot Vacuums 2026")
    assert card["rel"] == "/reviews/robot-vacuums/best-robot-vacuums-2026.html"


def test_deploy_root_index_skips_when_no_posts():
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    assert sd.deploy_root_index(niches=["laptops"], posts=[]) is False
    deployer.deploy_html.assert_not_called()


def test_deploy_root_index_deploys_with_content():
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    assert sd.deploy_root_index(niches=["laptops"], posts=[{"title": "T", "slug": "laptops"}]) is True
    deployer.deploy_html.assert_called_once()


def test_deploy_category_page_skips_when_no_posts():
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    assert sd.deploy_category_page("laptops", posts=[]) is False
    deployer.deploy_html.assert_not_called()


def test_deploy_category_page_deploys_with_posts():
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    assert sd.deploy_category_page("laptops", posts=[{"title": "T", "slug": "laptops"}]) is True
    deployer.deploy_html.assert_called_once()


def test_deploy_category_page_links_article_file():
    """Read-full-review link must point at the article file when recorded."""
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    ok = sd.deploy_category_page("tv", posts=[{
        "title": "Insignia 50 Fire TV Review",
        "filename": "insignia-50-fire-tv.html",
        "product_name": "Insignia 50",
    }], all_categories=["tv"])
    assert ok is True
    html, path = deployer.deploy_html.call_args[0]
    assert path == "tv/index.html"
    assert "/reviews/tv/insignia-50-fire-tv.html" in html


def test_deploy_category_hub_writes_canonical_reviews_path():
    """Brand-new category hubs deploy at the canonical /reviews/<niche>/ location."""
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    ok = sd.deploy_category_hub("tv", posts=[{
        "title": "Insignia 50 Fire TV Review",
        "filename": "insignia-50-fire-tv.html",
        "product_name": "Insignia 50",
    }], all_categories=["tv", "smart-home"])
    assert ok is True
    html, path = deployer.deploy_html.call_args[0]
    assert path == "reviews/tv/index.html"
    assert "smart-home" in html  # nav carries other categories


def test_deploy_category_hub_mirrors_newest_article():
    """A new-category hub after a content deploy mirrors that article, not a
    category listing, and keeps the /reviews/<niche>/ canonical."""
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    sd.deploy_content(
        "tv",
        {"post_title": "Insignia 50 Fire TV Review",
         "article_html": "<p>review</p>",
         "meta_description": "A first-time buyer guide.",
         "product_name": "Insignia 50"},
        all_categories=["tv"],
        article_filename="insignia-50-fire-tv.html",
    )
    ok = sd.deploy_category_hub("tv", posts=[
        {"title": "Insignia 50 Fire TV Review", "filename": "insignia-50-fire-tv.html"}
    ], all_categories=["tv"])
    assert ok is True
    html, path = deployer.deploy_html.call_args[0]
    assert path == "reviews/tv/index.html"
    assert 'rel="canonical" href="https://abvorn.com/reviews/tv/"' in html


def test_deploy_content_article_filename_write_path():
    """Opportunity articles write at their own dated URL and self-canonicalize."""
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    ok = sd.deploy_content(
        "tv",
        {"post_title": "Insignia 50 Fire TV Review",
         "article_html": "<p>review</p>",
         "meta_description": "A first-time buyer guide.",
         "product_name": "Insignia 50"},
        all_categories=["tv", "4k-monitors"],
        article_filename="insignia-50-fire-tv.html",
    )
    assert ok is True
    html, path = deployer.deploy_html.call_args[0]
    assert path == "reviews/tv/insignia-50-fire-tv.html"
    assert 'rel="canonical" href="https://abvorn.com/reviews/tv/insignia-50-fire-tv.html"' in html
    assert "4k-monitors" in html  # nav built from all_categories


def test_deploy_content_defaults_to_index():
    """Without an article_filename, behaviour is unchanged."""
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    sd.deploy_content("laptops", {"post_title": "Laptop Buying Guide 2026",
                                  "article_html": "<p>x</p>"})
    html, path = deployer.deploy_html.call_args[0]
    assert path == "reviews/laptops/index.html"


def test_repoint_hub_canonical_keeps_hub_url():
    """The hub mirror must advertise /reviews/<slug>/, never the dated file."""
    from run_cycle import _repoint_hub_canonical
    html = ('<link rel="canonical" href="https://abvorn.com/reviews/tv/x-2026-09-29.html">'
            '<meta property="og:url" content="https://abvorn.com/reviews/tv/x-2026-09-29.html">')
    out = _repoint_hub_canonical(html, "tv")
    assert '<link rel="canonical" href="https://abvorn.com/reviews/tv/">' in out
    assert '<meta property="og:url" content="https://abvorn.com/reviews/tv/">' in out


def test_build_article_page_self_canonical_for_dated_article():
    """A dated article canonicalizes to its own file URL, not the hub."""
    from run_cycle import build_article_page
    html = build_article_page(
        "tv", "TV", "Insignia 50 Review", "<p>x</p>", "", "Insignia 50",
        "desc", ["tv"], amazon_tag="viraltestco-20",
        canonical_url="https://abvorn.com/reviews/tv/insignia-50-2026-09-29.html",
    )
    assert ('<link rel="canonical" href='
            '"https://abvorn.com/reviews/tv/insignia-50-2026-09-29.html">') in html
    assert ('<meta property="og:url" content='
            '"https://abvorn.com/reviews/tv/insignia-50-2026-09-29.html">') in html


def test_build_article_page_defaults_to_hub_canonical():
    """Without canonical_url the page keeps the /reviews/<slug>/ hub canonical."""
    from run_cycle import build_article_page
    html = build_article_page(
        "tv", "TV", "Insignia 50 Review", "<p>x</p>", "", "Insignia 50",
        "desc", ["tv"], amazon_tag="viraltestco-20",
    )
    assert '<link rel="canonical" href="https://abvorn.com/reviews/tv/">' in html


def test_deployer_hub_canonical_delegate():
    """The src.deployment re-point delegate must re-point both tags.

    The deployer writes the newest dated article to both <file>.html and
    index.html; only the hub copy may claim the directory URL.
    """
    from src.deployment import _repoint_hub_canonical as deploy_repoint
    html = (
        '<link rel="canonical" '
        'href="https://abvorn.com/reviews/tv/insignia-50-2026-09-29.html">'
        '<meta property="og:url" '
        'content="https://abvorn.com/reviews/tv/insignia-50-2026-09-29.html">'
    )
    out = deploy_repoint(html, "tv")
    assert '<link rel="canonical" href="https://abvorn.com/reviews/tv/">' in out
    assert ('<meta property="og:url" content="https://abvorn.com/reviews/tv/">'
            in out)
    assert "insignia-50-2026-09-29.html" not in out


def test_product_placeholder_detection():
    """A product with no ASIN is not buyable; 'Top <niche> Pick' is the stub
    shape research_niche used to fabricate when every lookup failed."""
    from abvorn.agents.orchestrator import _product_is_placeholder, _products_are_placeholder
    stub = {"name": "Top tv Pick", "price": "Check Price",
            "url": "?tag=viraltestco-20"}
    real = {"name": "Roku 40-inch Select Series",
            "url": "https://www.amazon.com/dp/B0F1GF1KFC?tag=viraltestco-20"}
    assert _product_is_placeholder(stub) is True
    assert _product_is_placeholder(real) is False
    assert _product_is_placeholder({"name": "", "url": ""}) is True
    # ASIN in the name is enough even when the link form differs.
    assert _product_is_placeholder(
        {"name": "Roku 40 B0F1GF1KFC", "url": "https://www.amazon.com/s?k=roku"}
    ) is False
    assert _products_are_placeholder([stub]) is True
    assert _products_are_placeholder([stub, real]) is False
    # No products at all is not a placeholder payload: those are category pages
    # and they have always been deployable.
    assert _products_are_placeholder([]) is False


def test_deploy_content_refuses_placeholder_products():
    """The tv hub shipped one invented product and zero ASINs because a failed
    research run was published anyway. A product set with no ASIN anywhere must
    be refused at the deploy boundary, keeping the live page untouched."""
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    ok = sd.deploy_content(
        "tv",
        {"post_title": "2026 TV Buying Guide",
         "article_html": "<p>guide</p>",
         "products": [{"name": "Top tv Pick", "price": "Check Price",
                       "url": "?tag=viraltestco-20", "category": "best_overall"}]},
        all_categories=["tv"],
    )
    assert ok is False
    deployer.deploy_html.assert_not_called()


def test_productless_payload_never_becomes_the_hub_mirror():
    """A refused product-less publish must not leave a product-less mirror behind.

    deploy_category_hub() installs reviews/<niche>/index.html from _last_content.
    That assignment happens only after the products checks pass, so a refused
    payload can never become the hub page. The three product-less tv pages that
    shipped (zero ASINs, cards falling back to assets/tv.svg) predate the gate
    in 79a52210; this locks the invariant that stops them recurring.
    """
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    ok = sd.deploy_content(
        "tv",
        {"post_title": "2026 TV Buying Guide",
         "article_html": "<p>guide</p>",
         "products": []},
        all_categories=["tv"],
        require_products=True,
    )
    assert ok is False
    assert sd._last_content is None, "a refused payload must not be cached for mirroring"
    assert sd._last_niche is None
    deployer.deploy_html.assert_not_called()

    # With a real ASIN-backed product the mirror is installed as before.
    ok = sd.deploy_content(
        "tv",
        {"post_title": "2026 TV Buying Guide",
         "article_html": "<p>guide</p>",
         "products": [{"name": "Roku 40-inch Select Series",
                       "url": "https://www.amazon.com/dp/B0F1GF1KFC?tag=viraltestco-20"}]},
        all_categories=["tv"],
    )
    assert ok is True
    assert sd._last_content is not None


def test_deploy_content_allows_real_products():
    """The same page with a real, ASIN-backed product set still deploys."""
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    ok = sd.deploy_content(
        "tv",
        {"post_title": "2026 TV Buying Guide",
         "article_html": "<p>guide</p>",
         "products": [{"name": "Roku 40-inch Select Series",
                       "url": "https://www.amazon.com/dp/B0F1GF1KFC?tag=viraltestco-20"}]},
        all_categories=["tv"],
    )
    assert ok is True


def test_deploy_content_refuses_off_topic_title():
    """A real product set is not enough when the title is about something else.

    "Solar Panels Buying Guide" shipped under reviews/laptops/ and
    "First-Time Hotel Booking Guide" under reviews/robot-vacuums/ -- both with
    a real laptop/vacuum product set, both self-canonical. The products check
    cannot see this, because the payload genuinely had products; only the
    title's relationship to the niche can.
    """
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    ok = sd.deploy_content(
        "laptops",
        {"post_title": "Solar Panels Buying Guide for First-Time Buyers",
         "article_html": "<p>guide</p>",
         "products": [{"name": "Lenovo ThinkPad X1 Carbon",
                       "url": "https://www.amazon.com/dp/B0F1GF1KFC?tag=viraltestco-20"}]},
        all_categories=["laptops"],
    )
    assert ok is False
    deployer.deploy_html.assert_not_called()
    # The refused payload must not become the hub mirror either.
    assert sd._last_content is None
    assert sd._last_niche is None


def test_deploy_content_allows_on_topic_title_despite_no_slug_word():
    """The guard must not fire when the title is on-topic but never names the
    niche. 'Echo Show 5' says nothing about 'smart-home', yet the page belongs
    there; rejecting it would trade this bug for a worse one."""
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    ok = sd.deploy_content(
        "smart-home",
        {"post_title": "First-Time Buyer Guide: Echo Show 5 Review & Best Deal",
         "article_html": "<p>guide</p>",
         "products": [{"name": "Echo Show 5",
                       "url": "https://www.amazon.com/dp/B0F1GF1KFC?tag=viraltestco-20"}]},
        all_categories=["smart-home"],
    )
    assert ok is True

    html, path = deployer.deploy_html.call_args[0]
    assert path == "reviews/smart-home/index.html"
    assert "B0F1GF1KFC" in html


def test_scheduler_queue():
    """Should return the highest-priority item from queue."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "state.db"
        sched = Scheduler(state_db=str(db))
        sched.state.add_opportunity("test niche", score=0.9, search_volume=5000)
        sched.state.add_opportunity("low niche", score=0.2, search_volume=100)
        next_item = sched.get_next_opportunity()
        assert next_item is not None
        assert next_item["niche"] == "test niche"
        sched.state.close()


def test_scheduler_empty_queue():
    """Should return None when queue is empty."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "state.db"
        sched = Scheduler(state_db=str(db))
        assert sched.get_next_opportunity() is None
        sched.state.close()


def test_mark_complete():
    """Should mark an opportunity as completed."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "state.db"
        sched = Scheduler(state_db=str(db))
        sched.state.add_opportunity("test", 0.9)
        opp = sched.get_next_opportunity()
        assert opp is not None
        sched.mark_complete(opp["id"])
        assert sched.get_next_opportunity() is None
        sched.state.close()


# ── unpictured-product regression (tv + robot-vacuums, 2026-09-30) ─────────
# The live tv hub shipped three product cards whose media was a <span>Product</span>
# text tile, not a photo, and the robot-vacuums hub shipped no product grid at
# all. Both niches were absent from the OpenWebNinja cache, so research_niche
# fell through to its pure-LLM branch, which emits no image and no ASIN. The old
# detector only flagged names matching "Top ... Pick", so real-sounding invented
# models sailed through.

def test_product_without_asin_and_image_is_placeholder():
    """No ASIN *and* no photo is the pure-LLM shape, whatever the name says."""
    from abvorn.agents.orchestrator import _product_is_placeholder

    # Verbatim from the live tv hub -- reads real, is unbuyable and unpictured.
    assert _product_is_placeholder({
        "name": 'Sony Bravia XR90A9 65" OLED TV',
        "price": "Check Price",
        "url": "https://www.amazon.com/s?k=tv&tag=viraltestco-20",
        "image": "",
        "description": "Ultra-high-definition 4K OLED with quantum HDR 400.",
    }) is True
    # A scraped product is fine with either signal present.
    assert _product_is_placeholder({
        "name": "Sony Bravia XR90A9 65\" OLED TV",
        "image": "https://m.media-amazon.com/images/I/71abc._AC_SL1500_.jpg",
    }) is False
    assert _product_is_placeholder({
        "name": "Sony Bravia XR90A9 65\" OLED TV",
        "asin": "B0CX23V2ZK",
        "image": "",
    }) is False


def test_deploy_content_refuses_unpictured_llm_products():
    """The exact live tv payload must be refused at the deploy boundary."""
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    ok = sd.deploy_content(
        "tv",
        {"post_title": "2026 TV Buying Guide",
         "article_html": "<p>guide</p>",
         "products": [
             {"name": 'Sony Bravia XR90A9 65" OLED TV', "price": "Check Price",
              "url": "https://www.amazon.com/s?k=tv&tag=viraltestco-20", "image": ""},
             {"name": 'Samsung QN90B 55" Neo-QLED TV', "price": "Check Price",
              "url": "https://www.amazon.com/s?k=tv&tag=viraltestco-20", "image": ""},
         ]},
        all_categories=["tv"],
    )
    assert ok is False
    deployer.deploy_html.assert_not_called()


def test_deploy_content_require_products_blocks_productless_fresh_article():
    """robot-vacuums shipped a hub with no product grid at all. The fresh-publish
    path opts into require_products; the state-redeploy path must still work."""
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    ok = sd.deploy_content(
        "robot-vacuums",
        {"post_title": "2026 Robot Vacuum Buying Guide",
         "article_html": "<p>guide</p>",
         "products": []},
        all_categories=["robot-vacuums"],
        require_products=True,
    )
    assert ok is False
    deployer.deploy_html.assert_not_called()

    # Without the opt-in (state redeploy) the same payload is still deployable.
    deployer2 = _deployer()
    sd2 = SiteDeployer(deployer2, None)
    assert sd2.deploy_content(
        "laptops", {"post_title": "Laptop Buying Guide 2026",
                    "article_html": "<p>x</p>"},
        all_categories=["laptops"],
    ) is True