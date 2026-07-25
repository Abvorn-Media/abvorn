"""BrandEngine — merges global brand rules with per-site identity and audience persona."""

from .model import Site, BrandConfig, DNAProfile

GLOBAL_DEFAULTS = {
    "primary_color": "#1a73e8",
    "secondary_color": "#34a853",
}

GLOBAL_BANNED_PHRASES = [
    "game-changer", "cutting-edge", "dive into", "revolutionary",
    "best-in-class", "next-gen", "think outside the box",
]


def get_brand(site: Site, persona: dict | None = None) -> BrandConfig:
    primary = site.primary_color or GLOBAL_DEFAULTS["primary_color"]
    secondary = site.secondary_color or GLOBAL_DEFAULTS["secondary_color"]
    dna = get_dna_for_persona(persona)

    return BrandConfig(
        brand_name=site.name,
        brand_tagline=site.tagline or "",
        logo_text=site.logo_text,
        logo_icon=site.logo_icon or "",
        primary_color=primary,
        secondary_color=secondary,
        dna_profile=dna,
        voice_rules=site.voice_rules or {},
        domain=site.domain or "",
    )


def get_dna_for_persona(persona: dict | None) -> DNAProfile:
    if not persona:
        return DNAProfile.TECH
    traits = [t.lower() for t in persona.get("traits", [])]

    tech_keywords = {"analytical", "tech-savvy", "detail-oriented", "spec-driven", "technical"}
    warm_keywords = {"family-oriented", "practical", "value-conscious", "lifestyle", "casual"}
    premium_keywords = {"quality-seeking", "brand-conscious", "discerning", "luxury", "premium"}

    tech_score = sum(1 for t in traits if t in tech_keywords)
    warm_score = sum(1 for t in traits if t in warm_keywords)
    premium_score = sum(1 for t in traits if t in premium_keywords)

    if premium_score > tech_score and premium_score > warm_score:
        return DNAProfile.PREMIUM
    elif warm_score > tech_score:
        return DNAProfile.WARM
    return DNAProfile.TECH
