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
    """Opportunity articles write inside the category, canonical stays the hub."""
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
    assert 'href="https://abvorn.com/reviews/tv/"' in html  # canonical is the category hub
    assert "4k-monitors" in html  # nav built from all_categories


def test_deploy_content_defaults_to_index():
    """Without an article_filename, behaviour is unchanged."""
    deployer = _deployer()
    sd = SiteDeployer(deployer, None)
    sd.deploy_content("laptops", {"post_title": "T", "article_html": "<p>x</p>"})
    html, path = deployer.deploy_html.call_args[0]
    assert path == "reviews/laptops/index.html"


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
    html, path = deployer.deploy_html.call_args[0]
    assert path == "reviews/tv/index.html"
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