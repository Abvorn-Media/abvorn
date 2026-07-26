"""Tests for NetworkDashboard — root directory and per-site homepages."""
from unittest.mock import MagicMock
from abvorn.deploy.dashboard import NetworkDashboard
from abvorn.sites.model import Site


def test_deploy_root_index():
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"site_id":"s1","slug":"tech","name":"Tech","tagline":"Awesome tech",'
        '"logo_text":"T","logo_icon":"T","primary_color":"#1a73e8",'
        '"secondary_color":"#34a853","voice_rules":{},"niches":["tv","laptop"],'
        '"domain":"","status":"active","created_at":""}]'
    )
    deployer = MagicMock()
    dashboard = NetworkDashboard(state, deployer)
    result = dashboard.deploy_root_index()
    assert result is True
    assert deployer.deploy_html.called
    # Should be deployed to root path
    args, _ = deployer.deploy_html.call_args
    assert "index.html" in args[1] or args[1].strip() == "" or args[1] == ""


def test_deploy_site_homepage():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    deployer = MagicMock()
    dashboard = NetworkDashboard(state, deployer)
    site = Site(site_id="s1", slug="tech", name="Tech", tagline="", logo_text="T", logo_icon="T",
                primary_color="#000", secondary_color="#fff", voice_rules={},
                niches=["tv"], status="active")
    result = dashboard.deploy_site_homepage(site)
    assert result is True
