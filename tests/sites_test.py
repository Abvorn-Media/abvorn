"""Tests for Site model and BrandConfig dataclasses."""
import pytest
from abvorn.sites.model import Site, BrandConfig, DNAProfile

def test_site_minimal_config():
    s = Site(
        site_id="s1",
        slug="tech-gadgets",
        name="Tech & Gadgets",
        tagline="Honest reviews for smart shoppers",
        logo_text="Tech & Gadgets",
        logo_icon="🔌",
        primary_color="#1a73e8",
        secondary_color="#34a853",
        voice_rules={},
        niches=["tv", "laptop", "monitor"],
        status="active",
    )
    assert s.slug == "tech-gadgets"
    assert s.primary_color == "#1a73e8"
    assert "tv" in s.niches

def test_site_with_domain():
    s = Site(
        site_id="s2",
        slug="home-kitchen",
        name="Home & Kitchen",
        tagline="",
        logo_text="Home & Kitchen",
        logo_icon="🏠",
        primary_color="#e8a87c",
        secondary_color="#41b3a3",
        voice_rules={},
        niches=[],
        domain="homekitchen.com",
        status="active",
    )
    assert s.domain == "homekitchen.com"

def test_brand_config_immutable():
    bc = BrandConfig(
        brand_name="Tech & Gadgets",
        brand_tagline="Honest reviews",
        logo_text="Tech & Gadgets",
        logo_icon="🔌",
        primary_color="#1a73e8",
        secondary_color="#34a853",
        dna_profile=DNAProfile.TECH,
        voice_rules={"tone": "casual"},
        domain="",
    )
    assert bc.brand_name == "Tech & Gadgets"
    assert bc.dna_profile == DNAProfile.TECH
    with pytest.raises(AttributeError):
        bc.brand_name = "Hacked"

def test_brand_config_no_voice_rules():
    bc = BrandConfig(
        brand_name="Test",
        brand_tagline="",
        logo_text="Test",
        logo_icon="T",
        primary_color="#000",
        secondary_color="#fff",
        dna_profile=DNAProfile.WARM,
        voice_rules={},
        domain="",
    )
    assert bc.voice_rules == {}

def test_dna_profile_values():
    assert DNAProfile.TECH.value == "tech"
    assert DNAProfile.WARM.value == "warm"
    assert DNAProfile.PREMIUM.value == "premium"


"""Tests for SiteRegistry."""
import pytest, json
from unittest.mock import MagicMock
from abvorn.sites.model import Site
from abvorn.sites.registry import SiteRegistry


def test_register_and_get():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    registry = SiteRegistry(state)
    site = Site(
        site_id="s1",
        slug="tech-gadgets",
        name="Tech & Gadgets",
        tagline="Honest reviews",
        logo_text="Tech & Gadgets",
        logo_icon="🔌",
        primary_color="#1a73e8",
        secondary_color="#34a853",
        voice_rules={},
        niches=["tv", "laptop"],
        status="active",
    )
    registry.register(site)
    assert state.set_meta.called

def test_find_by_niche_match():
    state = MagicMock()
    state.get_meta.return_value = json.dumps([
        {"site_id":"s1","slug":"tech-gadgets","name":"Tech & Gadgets","tagline":"","logo_text":"TG","logo_icon":"T","primary_color":"#000","secondary_color":"#fff","voice_rules":{},"niches":["tv","laptop"],"domain":"","status":"active","created_at":""}
    ])
    registry = SiteRegistry(state)
    site = registry.find_by_niche("tv")
    assert site is not None
    assert site.slug == "tech-gadgets"

def test_find_by_niche_miss():
    state = MagicMock()
    state.get_meta.return_value = json.dumps([
        {"site_id":"s1","slug":"tech-gadgets","name":"Tech & Gadgets","tagline":"","logo_text":"TG","logo_icon":"T","primary_color":"#000","secondary_color":"#fff","voice_rules":{},"niches":["tv","laptop"],"domain":"","status":"active","created_at":""}
    ])
    registry = SiteRegistry(state)
    site = registry.find_by_niche("earbuds")
    assert site is None

def test_auto_assign_miss():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    registry = SiteRegistry(state)
    assert registry.auto_assign("earbuds") is None

def test_assign_niche():
    state = MagicMock()
    state.get_meta.return_value = json.dumps([
        {"site_id":"s1","slug":"tech-gadgets","name":"Tech & Gadgets","tagline":"","logo_text":"TG","logo_icon":"T","primary_color":"#000","secondary_color":"#fff","voice_rules":{},"niches":["tv"],"domain":"","status":"active","created_at":""}
    ])
    registry = SiteRegistry(state)
    registry.assign_niche("s1", "laptop")
    call_data = json.loads(state.set_meta.call_args[0][1])
    found = [s for s in call_data if s["site_id"] == "s1"][0]
    assert "laptop" in found["niches"]

def test_list_sites():
    state = MagicMock()
    state.get_meta.return_value = json.dumps([
        {"site_id":"s1","slug":"a","name":"A","tagline":"","logo_text":"A","logo_icon":"a","primary_color":"#000","secondary_color":"#fff","voice_rules":{},"niches":[],"domain":"","status":"active","created_at":""},
        {"site_id":"s2","slug":"b","name":"B","tagline":"","logo_text":"B","logo_icon":"b","primary_color":"#000","secondary_color":"#fff","voice_rules":{},"niches":[],"domain":"","status":"active","created_at":""},
    ])
    registry = SiteRegistry(state)
    assert len(registry.list()) == 2

def test_count_sites():
    state = MagicMock()
    state.get_meta.return_value = json.dumps([
        {"site_id":"s1","slug":"a","name":"A","tagline":"","logo_text":"A","logo_icon":"a","primary_color":"#000","secondary_color":"#fff","voice_rules":{},"niches":[],"domain":"","status":"active","created_at":""},
    ])
    registry = SiteRegistry(state)
    assert registry.count() == 1
