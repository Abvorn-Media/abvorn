"""Tests for BrandEngine — global + per-site brand merging."""
import pytest
from abvorn.sites.model import Site, BrandConfig, DNAProfile
from abvorn.sites.brand import get_brand, get_dna_for_persona


def test_get_brand_uses_site_values():
    site = Site(
        site_id="s1",
        slug="tech-gadgets",
        name="Tech & Gadgets",
        tagline="Honest reviews for smart shoppers",
        logo_text="Tech & Gadgets",
        logo_icon="🔌",
        primary_color="#1a73e8",
        secondary_color="#34a853",
        voice_rules={"tone": "casual"},
        niches=["tv"],
        status="active",
    )
    bc = get_brand(site)
    assert bc.brand_name == "Tech & Gadgets"
    assert bc.brand_tagline == "Honest reviews for smart shoppers"
    assert bc.primary_color == "#1a73e8"
    assert bc.voice_rules["tone"] == "casual"


def test_get_brand_falls_back_to_global_when_empty():
    site = Site(
        site_id="s2",
        slug="empty",
        name="Empty",
        tagline="",
        logo_text="Empty",
        logo_icon="E",
        primary_color="",
        secondary_color="",
        voice_rules={},
        niches=[],
        status="active",
    )
    bc = get_brand(site)
    assert bc.primary_color != ""  # falls back to global default


def test_get_brand_default_dna():
    site = Site(
        site_id="s1",
        slug="tech",
        name="Tech",
        tagline="",
        logo_text="Tech",
        logo_icon="T",
        primary_color="#000",
        secondary_color="#fff",
        voice_rules={},
        niches=[],
        status="active",
    )
    bc = get_brand(site, persona=None)
    assert bc.dna_profile in (DNAProfile.TECH, DNAProfile.WARM, DNAProfile.PREMIUM)


def test_dna_from_technical_persona():
    persona = {"traits": ["analytical", "tech-savvy", "detail-oriented"]}
    dna = get_dna_for_persona(persona)
    assert dna == DNAProfile.TECH


def test_dna_from_lifestyle_persona():
    persona = {"traits": ["family-oriented", "practical", "value-conscious"]}
    dna = get_dna_for_persona(persona)
    assert dna == DNAProfile.WARM


def test_dna_from_premium_persona():
    persona = {"traits": ["quality-seeking", "brand-conscious", "discerning"]}
    dna = get_dna_for_persona(persona)
    assert dna == DNAProfile.PREMIUM


def test_dna_fallback_when_no_persona():
    dna = get_dna_for_persona(None)
    assert dna == DNAProfile.TECH
