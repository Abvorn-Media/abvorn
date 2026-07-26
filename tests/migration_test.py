"""Tests for BootstrapMigration."""
from unittest.mock import MagicMock
from abvorn.sites.migration import BootstrapMigration


def test_needs_migration_when_empty():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    migration = BootstrapMigration(state, MagicMock())
    assert migration.needs_migration() is True


def test_needs_migration_when_sites_exist():
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"site_id":"s1","slug":"tech","name":"Tech","tagline":"","logo_text":"T",'
        '"logo_icon":"T","primary_color":"#000","secondary_color":"#fff",'
        '"voice_rules":{},"niches":["tv"],"domain":"","status":"active","created_at":""}]'
    )
    migration = BootstrapMigration(state, MagicMock())
    assert migration.needs_migration() is False


def test_run_creates_site_and_redirects():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    deployer = MagicMock()
    deployer.deploy_html.return_value = {"status": "success"}
    migration = BootstrapMigration(state, deployer)
    results = migration.run()
    assert any("Created" in r for r in results)
    assert any("redirect" in r for r in results)
    assert deployer.deploy_html.call_count == len(migration.NICHE_PREFIXES)


def test_run_skips_when_sites_exist():
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"site_id":"s1","slug":"tech","name":"Tech","tagline":"","logo_text":"T",'
        '"logo_icon":"T","primary_color":"#000","secondary_color":"#fff",'
        '"voice_rules":{},"niches":[],"domain":"","status":"active","created_at":""}]'
    )
    deployer = MagicMock()
    migration = BootstrapMigration(state, deployer)
    results = migration.run()
    assert any("skip" in r.lower() for r in results)
    assert deployer.deploy_html.call_count == 0
