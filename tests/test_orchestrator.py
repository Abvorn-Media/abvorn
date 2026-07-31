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