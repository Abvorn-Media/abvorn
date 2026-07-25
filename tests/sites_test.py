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
