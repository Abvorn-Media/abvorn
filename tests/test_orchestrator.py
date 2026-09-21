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