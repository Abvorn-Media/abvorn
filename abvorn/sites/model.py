"""Site model, BrandConfig, and DNAProfile — per-site identity data structures."""

from dataclasses import dataclass, field
from enum import Enum


class DNAProfile(Enum):
    TECH = "tech"
    WARM = "warm"
    PREMIUM = "premium"


@dataclass(frozen=True)
class BrandConfig:
    brand_name: str
    brand_tagline: str
    logo_text: str
    logo_icon: str
    primary_color: str
    secondary_color: str
    dna_profile: DNAProfile
    voice_rules: dict
    domain: str


@dataclass
class Site:
    site_id: str
    slug: str
    name: str
    tagline: str
    logo_text: str
    logo_icon: str
    primary_color: str
    secondary_color: str
    voice_rules: dict
    niches: list = field(default_factory=list)
    domain: str = ""
    status: str = "active"
    created_at: str = ""
