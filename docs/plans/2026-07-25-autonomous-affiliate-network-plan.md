# Autonomous Affiliate Network Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Abvorn from a single-site content engine into a multi-site affiliate network where each category gets its own branded destination with persona-driven design, shared intelligence, and cross-linking.

**Architecture:** A `Site` model + `SiteRegistry` in the state DB define per-site identity (name, colors, logo, niche assignment). A `BrandEngine` merges global brand rules with per-site config and audience persona to produce a full `BrandConfig` (including design DNA profile). The existing `GitHubDeployer` takes `BrandConfig` as a parameter, rendering each page with that site's identity. `CrossLinker` adds contextual sister-site links. Telegram dashboard gains per-site views. Existing content at `docs/{niche}/` gets redirect HTML to `docs/{site-slug}/{niche}/`.

**Tech Stack:** Python 3.14, SQLite (AbvornState), GitHub Pages (static deploy)

## Global Constraints

- All state stored in existing SQLite via `AbvornState` — no new databases or external services
- Template changes must preserve all existing CSS and interactive features (UIX reactions, comments, shares)
- Output path changes: `docs/{niche}/` → `docs/{site-slug}/{niche}/`
- Old paths must redirect via HTML meta refresh
- CrossLinker failures must never block deploy — logged and skipped
- Brand config must fall back to global defaults when per-site config is empty
- All design DNA profiles share the same HTML skeleton — only CSS variable overrides change
- All tests must use existing test patterns (mocked state, no real API calls)

---

### Task 1: Site Model + BrandConfig Dataclasses + Tests

**Files:**
- Create: `abvorn/sites/__init__.py`
- Create: `abvorn/sites/model.py`
- Test: `tests/sites_test.py`

**Interfaces:**
- Consumes: nothing (pure data)
- Produces: `Site` dataclass, `BrandConfig` dataclass, `DNAProfile` enum (`TECH`, `WARM`, `PREMIUM`)

- [ ] **Step 1: Write the failing test**

```python
"""Tests for Site model and BrandConfig dataclasses."""
import pytest
from dataclasses import dataclass
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sites_test.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Write minimal implementation**

Create `abvorn/sites/__init__.py`:
```python
```

Create `abvorn/sites/model.py`:
```python
"""Site model, BrandConfig, and DNAProfile — per-site identity data structures."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/sites_test.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/sites_test.py abvorn/sites/__init__.py abvorn/sites/model.py
git commit -m "feat: add Site model and BrandConfig dataclasses"
```

---

### Task 2: SiteRegistry + State DB Schema + Tests

**Files:**
- Create: `abvorn/sites/registry.py`
- Modify: `abvorn/core/state.py` (add `sites` table to schema)
- Test: `tests/sites_test.py` (append)

**Interfaces:**
- Consumes: `Site` dataclass (from Task 1), `AbvornState` (existing)
- Produces: `SiteRegistry` class with `register()`, `get()`, `find_by_niche()`, `assign_niche()`, `auto_assign()`, `list()`, `count()`

- [ ] **Step 1: Write the failing tests** (append to `tests/sites_test.py`)

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/sites_test.py::test_register_and_get tests/sites_test.py::test_find_by_niche_match tests/sites_test.py::test_find_by_niche_miss tests/sites_test.py::test_auto_assign_miss tests/sites_test.py::test_assign_niche tests/sites_test.py::test_list_sites tests/sites_test.py::test_count_sites -v`
Expected: FAIL with ImportError for SiteRegistry

- [ ] **Step 3: Add `sites` table schema to `abvorn/core/state.py`**

In the `SCHEMA` dict or `_init_tables` method, add:

```python
self._execute("""
    CREATE TABLE IF NOT EXISTS sites (
        site_id TEXT PRIMARY KEY,
        slug TEXT UNIQUE,
        name TEXT,
        tagline TEXT DEFAULT '',
        logo_text TEXT,
        logo_icon TEXT DEFAULT '',
        primary_color TEXT DEFAULT '#1a73e8',
        secondary_color TEXT DEFAULT '#34a853',
        voice_rules TEXT DEFAULT '{}',
        niches TEXT DEFAULT '[]',
        domain TEXT DEFAULT '',
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT ''
    )
""")
```

- [ ] **Step 4: Write `abvorn/sites/registry.py`**

```python
"""SiteRegistry — manages per-site identity config in state DB."""

import json
from .model import Site

STORAGE_KEY = "sites"


class SiteRegistry:
    """CRUD for Site objects. Stored as JSON in AbvornState meta."""

    def __init__(self, state):
        self._state = state

    def register(self, site: Site):
        sites = self._load_all()
        sites.append(site)
        self._save_all(sites)

    def get(self, site_id: str) -> Site | None:
        for s in self._load_all():
            if s.site_id == site_id:
                return s
        return None

    def find_by_niche(self, niche_slug: str) -> Site | None:
        for s in self._load_all():
            if niche_slug in s.niches:
                return s
        return None

    def assign_niche(self, site_id: str, niche_slug: str):
        sites = self._load_all()
        for s in sites:
            if s.site_id == site_id:
                if niche_slug not in s.niches:
                    s.niches.append(niche_slug)
                break
        self._save_all(sites)

    def auto_assign(self, niche_slug: str) -> Site | None:
        return self.find_by_niche(niche_slug)

    def list(self) -> list:
        return self._load_all()

    def count(self) -> int:
        return len(self._load_all())

    def _load_all(self) -> list:
        raw = self._state.get_meta(STORAGE_KEY, "[]")
        data = json.loads(raw) if isinstance(raw, str) else raw
        return [Site(**s) if not isinstance(s, Site) else s for s in data]

    def _save_all(self, sites: list):
        raw = json.dumps([s.__dict__ if hasattr(s, '__dict__') else s for s in sites], default=str)
        self._state.set_meta(STORAGE_KEY, raw)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/sites_test.py -v`
Expected: PASS (12 passed — 5 from Task 1 + 7 from Task 2)

- [ ] **Step 6: Commit**

```bash
git add tests/sites_test.py abvorn/sites/registry.py abvorn/core/state.py
git commit -m "feat: add SiteRegistry and state DB schema"
```

---

### Task 3: BrandEngine + Design DNA Mapping + Tests

**Files:**
- Create: `abvorn/sites/brand.py`
- Test: `tests/brand_test.py`

**Interfaces:**
- Consumes: `Site` dataclass, `BrandConfig` dataclass, `DNAProfile` enum (from Task 1)
- Produces: `get_brand(site: Site, persona: dict | None = None) -> BrandConfig`

- [ ] **Step 1: Write the failing test**

Create `tests/brand_test.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/brand_test.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write `abvorn/sites/brand.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/brand_test.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/brand_test.py abvorn/sites/brand.py
git commit -m "feat: add BrandEngine with design DNA mapping"
```

---

### Task 4: Brand-Aware Template Rendering + Design DNA CSS + Tests

**Files:**
- Modify: `abvorn/deploy/github.py` (render function accepts `BrandConfig`, injects DNA CSS variables, brand name/logo/colors)
- Test: `tests/deploy_test.py`

**Interfaces:**
- Consumes: `BrandConfig` dataclass (from Task 3)
- Produces: Modified `GitHubDeployer.render()` that accepts brand config, returns brand-styled HTML

- [ ] **Step 1: Write the failing test**

Append to `tests/deploy_test.py`:

```python
"""Tests for brand-aware deployment."""
from abvorn.sites.model import BrandConfig, DNAProfile
from abvorn.deploy.github import GitHubDeployer


def test_render_with_brand_config():
    deployer = GitHubDeployer("test/repo", "token")
    brand = BrandConfig(
        brand_name="Tech & Gadgets",
        brand_tagline="Honest reviews",
        logo_text="Tech & Gadgets",
        logo_icon="🔌",
        primary_color="#1a73e8",
        secondary_color="#34a853",
        dna_profile=DNAProfile.TECH,
        voice_rules={},
        domain="",
    )
    html = deployer.render_page(
        title="Best TVs of 2026",
        content="<p>Test content</p>",
        slug="best-tvs",
        brand=brand,
    )
    assert "Tech & Gadgets" in html or "Tech" in html
    assert "🔌" in html
    assert "#1a73e8" in html
    assert dna_css_for(DNAProfile.TECH) in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/deploy_test.py::test_render_with_brand_config -v`
Expected: FAIL (render_page doesn't accept brand param yet)

- [ ] **Step 3: Modify `GitHubDeployer.render_page()` to accept optional `brand: BrandConfig | None`**

Generate a CSS string for the DNA profile:

```python
DNA_CSS = {
    DNAProfile.TECH: (
        "--font-family: 'Inter', -apple-system, sans-serif;\n"
        "--border-radius: 2px;\n"
        "--card-style: flat;\n"
        "--button-style: outline;\n"
        "--button-radius: 2px;\n"
        "--image-radius: 2px;\n"
        "--spacing-unit: 8px;\n"
        "--heading-weight: 700;\n"
    ),
    DNAProfile.WARM: (
        "--font-family: 'Nunito', -apple-system, sans-serif;\n"
        "--border-radius: 12px;\n"
        "--card-style: shadow;\n"
        "--button-style: filled;\n"
        "--button-radius: 24px;\n"
        "--image-radius: 16px;\n"
        "--spacing-unit: 12px;\n"
        "--heading-weight: 600;\n"
    ),
    DNAProfile.PREMIUM: (
        "--font-family: 'Playfair Display', 'Lora', serif;\n"
        "--border-radius: 0px;\n"
        "--card-style: elevated;\n"
        "--button-style: ghost;\n"
        "--button-radius: 0px;\n"
        "--image-radius: 0px;\n"
        "--spacing-unit: 16px;\n"
        "--heading-weight: 400;\n"
    ),
}
```

In the render method:
- If `brand` is None, use defaults (current behavior)
- Inject `<body class="dna-{brand.dna_profile.value}">`
- Inject DNA CSS variables into `<style>` block
- Replace brand name in `<title>`, header, footer
- Set `og:site_name` to brand name

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/deploy_test.py::test_render_with_brand_config -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add abvorn/deploy/github.py tests/deploy_test.py
git commit -m "feat: brand-aware template with design DNA CSS variables"
```

---

### Task 5: SiteAwareDeployer Wrapper + Tests

**Files:**
- Create: `abvorn/deploy/site_deployer.py`
- Test: `tests/deploy_test.py` (append)

**Interfaces:**
- Consumes: `SiteRegistry`, `GitHubDeployer`, `get_brand()` (from Task 3)
- Produces: `SiteAwareDeployer` class — wraps `GitHubDeployer`, resolves brand via SiteRegistry before each deploy, renders site homepage after

- [ ] **Step 1: Write the failing test**

```python
"""Tests for SiteAwareDeployer."""
from unittest.mock import MagicMock, patch
from abvorn.deploy.site_deployer import SiteAwareDeployer
from abvorn.sites.model import Site


def test_site_aware_deployer_looks_up_site():
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"site_id":"s1","slug":"tech-gadgets","name":"Tech & Gadgets",'
        '"tagline":"","logo_text":"TG","logo_icon":"T","primary_color":"#000",'
        '"secondary_color":"#fff","voice_rules":{},"niches":["tv"],'
        '"domain":"","status":"active","created_at":""}]'
    )
    inner = MagicMock()
    inner.render_page.return_value = "<html></html>"
    deployer = SiteAwareDeployer(inner, state)
    deployer.deploy_niche("tv", {"title":"Test","content":"<p>Test</p>"})
    assert inner.render_page.called

def test_site_aware_deployer_no_site_found():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    inner = MagicMock()
    deployer = SiteAwareDeployer(inner, state)
    result = deployer.deploy_niche("unknown", {"title":"Test","content":"<p>Test</p>"})
    assert result is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/deploy_test.py::test_site_aware_deployer_looks_up_site tests/deploy_test.py::test_site_aware_deployer_no_site_found -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write `abvorn/deploy/site_deployer.py`**

```python
"""SiteAwareDeployer — wraps GitHubDeployer with per-site brand resolution."""

import logging
from ..sites.registry import SiteRegistry
from ..sites.brand import get_brand

logger = logging.getLogger("abvorn.deploy.site_deployer")


class SiteAwareDeployer:
    """Delegates to GitHubDeployer, enriching output with per-site brand config."""

    def __init__(self, inner_deployer, state):
        self._inner = inner_deployer
        self._registry = SiteRegistry(state)

    def deploy_niche(self, niche_slug: str, content: dict, persona: dict | None = None) -> bool:
        site = self._registry.find_by_niche(niche_slug)
        if not site:
            logger.warning(f"No site found for niche '{niche_slug}'")
            return False

        brand = get_brand(site, persona)
        output_path = f"{site.slug}/{niche_slug}"
        html = self._inner.render_page(
            title=content.get("title", ""),
            content=content.get("content", ""),
            slug=content.get("slug", niche_slug),
            brand=brand,
        )
        try:
            self._inner.deploy_html(html, output_path)
            return True
        except Exception as e:
            logger.error(f"Deploy failed for {niche_slug}: {e}")
            return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/deploy_test.py::test_site_aware_deployer_looks_up_site tests/deploy_test.py::test_site_aware_deployer_no_site_found -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add abvorn/deploy/site_deployer.py tests/deploy_test.py
git commit -m "feat: SiteAwareDeployer wrapper with brand resolution"
```

---

### Task 6: Redirect Generator + Tests

**Files:**
- Create: `abvorn/deploy/redirect.py`
- Create: `tests/redirect_test.py`

**Interfaces:**
- Produces: `generate_redirect_html(target_path: str) -> str`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for redirect HTML generator."""
from abvorn.deploy.redirect import generate_redirect_html


def test_redirect_to_site_path():
    html = generate_redirect_html("/tech-gadgets/tv/")
    assert "0; url=/tech-gadgets/tv/" in html
    assert "meta http-equiv" in html

def test_redirect_to_domain():
    html = generate_redirect_html("https://techandgadgets.com/tv/")
    assert "0; url=https://techandgadgets.com/tv/" in html

def test_redirect_is_valid_html():
    html = generate_redirect_html("/new-path/")
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/redirect_test.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write `abvorn/deploy/redirect.py`**

```python
"""Redirect HTML generator — meta refresh for GitHub Pages path migrations."""


def generate_redirect_html(target_url: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta http-equiv="refresh" content="0; url={target_url}">
<link rel="canonical" href="{target_url}">
</head>
<body>
<p>Redirecting to <a href="{target_url}">{target_url}</a>...</p>
</body>
</html>"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/redirect_test.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add abvorn/deploy/redirect.py tests/redirect_test.py
git commit -m "feat: redirect HTML generator for path migration"
```

---

### Task 7: CrossLinker + Tests

**Files:**
- Create: `abvorn/deploy/crosslinker.py`
- Test: `tests/crosslinker_test.py`

**Interfaces:**
- Consumes: `SiteRegistry` (from Task 2)
- Produces: `CrossLinker` class with `inject_links(post_content, niche_slug) -> str`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for CrossLinker — contextual sister-site links."""
from unittest.mock import MagicMock
from abvorn.deploy.crosslinker import CrossLinker
from abvorn.sites.model import Site


def test_crosslinker_no_sister_sites():
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"site_id":"s1","slug":"tech","name":"Tech","tagline":"",'
        '"logo_text":"T","logo_icon":"T","primary_color":"#000",'
        '"secondary_color":"#fff","voice_rules":{},"niches":["tv","laptop"],'
        '"domain":"","status":"active","created_at":""}]'
    )
    cl = CrossLinker(state)
    result = cl.inject_links("<p>Some content</p>", "tv")
    assert result == "<p>Some content</p>"

def test_crosslinker_adds_link_when_sister_exists():
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"site_id":"s1","slug":"tech","name":"Tech","tagline":"",'
        '"logo_text":"T","logo_icon":"T","primary_color":"#000",'
        '"secondary_color":"#fff","voice_rules":{},"niches":["tv"],'
        '"domain":"","status":"active","created_at":""},'
        '{"site_id":"s2","slug":"home","name":"Home","tagline":"",'
        '"logo_text":"H","logo_icon":"H","primary_color":"#000",'
        '"secondary_color":"#fff","voice_rules":{},"niches":["vacuum"],'
        '"domain":"","status":"active","created_at":""}]'
    )
    from abvorn.intel.engine import CrossNicheIntelligence
    cl = CrossLinker(state)
    with MagicMock() as mock_intel:
        mock_intel.compute_niche_similarity.return_value = {"vacuum": 0.5}
        result = cl.inject_links("<p>Great for your home.</p>", "tv")
        assert len(result) > len("<p>Great for your home.</p>")

def test_crosslinker_graceful_failure():
    state = MagicMock()
    state.get_meta.side_effect = Exception("DB error")
    cl = CrossLinker(state)
    result = cl.inject_links("<p>Content</p>", "tv")
    assert result == "<p>Content</p>"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/crosslinker_test.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write `abvorn/deploy/crosslinker.py`**

```python
"""CrossLinker — injects contextual cross-site links into posts."""

import logging
from ..sites.registry import SiteRegistry

logger = logging.getLogger("abvorn.deploy.crosslinker")
MAX_LINKS = 2


class CrossLinker:
    """Adds sister-site contextual links after content generation."""

    def __init__(self, state):
        self._registry = SiteRegistry(state)

    def inject_links(self, html_content: str, niche_slug: str) -> str:
        try:
            site = self._registry.find_by_niche(niche_slug)
            if not site:
                return html_content

            sister_sites = [s for s in self._registry.list() if s.site_id != site.site_id]
            if not sister_sites:
                return html_content

            links_added = 0
            for sister in sister_sites:
                if links_added >= MAX_LINKS:
                    break
                for sister_niche in sister.niches:
                    if links_added >= MAX_LINKS:
                        break
                    link_text = f"Check out our guide to <a href='/{sister.slug}/{sister_niche}/'>{sister_niche.replace('-', ' ').title()}</a>"
                    html_content += f"\n<p>{link_text}</p>"
                    links_added += 1
            return html_content
        except Exception as e:
            logger.debug(f"CrossLinker failed: {e}")
            return html_content
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/crosslinker_test.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add abvorn/deploy/crosslinker.py tests/crosslinker_test.py
git commit -m "feat: CrossLinker for contextual sister-site links"
```

---

### Task 8: Analytics Site-ID Filter + Tests

**Files:**
- Modify: `abvorn/analytics/engine.py` (add `site_id` param to insight report)
- Test: `tests/analytics_test.py`

**Interfaces:**
- Produces: `AnalyticsEngine.insight_report(site_id: str | None = None) -> dict`

- [ ] **Step 1: Write the failing test**

```python
def test_analytics_site_filter():
    from abvorn.analytics.engine import AnalyticsEngine
    engine = AnalyticsEngine(ga4_client=MagicMock(), state=MagicMock())
    report = engine.insight_report(site_id="tech-gadgets")
    assert isinstance(report, dict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/analytics_test.py -v`
Expected: At least the new test fails (insight_report doesn't accept site_id)

- [ ] **Step 3: Modify `AnalyticsEngine.insight_report()`**

In the method signature, add `site_id: str | None = None`. When site_id is present, prefix the page path filter with `/{site_id}/` in the GA4 query dimension filter.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/analytics_test.py -v`
Expected: All passed (7 existing + 1 new = 8)

- [ ] **Step 5: Commit**

```bash
git add abvorn/analytics/engine.py tests/analytics_test.py
git commit -m "feat: analytics site_id filter for per-site traffic reports"
```

---

### Task 9: Telegram Commands + Tests

**Files:**
- Modify: `abvorn/deploy/notifier.py` (add `/sites`, `/site`, `/predict` updates)
- Test: `tests/test_notifier.py` or `tests/test_agents.py` (existing command tests)

- [ ] **Step 1: Write failing tests**

```python
def test_telegram_sites_command_with_registry():
    from abvorn.deploy.notifier import TelegramNotifier
    n = TelegramNotifier(token="t", chat_id="c")
    n._site_registry = MagicMock()
    n._site_registry.list.return_value = [
        Site(site_id="s1", slug="tech", name="Tech", tagline="", logo_text="T", logo_icon="T",
             primary_color="#000", secondary_color="#fff", voice_rules={},
             niches=["tv", "laptop"], status="active")
    ]
    resp = n.process_command("/sites")
    assert "Tech" in resp

def test_telegram_traffic_with_site_arg():
    n = TelegramNotifier(token="t", chat_id="c")
    n._analytics_engine = MagicMock()
    n._analytics_engine.insight_report.return_value = {"pages": [], "summary": "Traffic report"}
    resp = n.process_command("/traffic tech-gadgets")
    assert "tech-gadgets" in resp or "Traffic" in resp
```

- [ ] **Step 2: Run test to verify they fail**

Run the relevant test file

- [ ] **Step 3: Add handlers to `TelegramNotifier.process_command()`**

Add to the COMMANDS dict:
```python
"/sites": "List all sites and their niches",
"/site <slug>": "Show site details",
```

Add handlers:
- `/sites` → calls `self._site_registry.list()`, formats name + slug + niche count
- `/site <slug>` → finds site, shows full config
- Update `/traffic <site>` → passes site_id to `insight_report(site_id=arg)`

- [ ] **Step 4: Run test to verify they pass**

- [ ] **Step 5: Commit**

---

### Task 10: Dashboard + Network Directory + Tests

**Files:**
- Modify: `abvorn/deploy/dashboard.py` (render root + per-site dashboards)
- Modify: `abvorn/deploy/github.py` (deploy site homepage after niche deploy)
- Test: `tests/dashboard_test.py`

- [ ] **Step 1: Write failing tests**

- [ ] **Step 2: Run to verify fail**

- [ ] **Step 3: Implement network directory page**

Root `index.html` lists all sites. Each site card shows name, tagline, niche list, link to `/{slug}/`. Footer has "Powered by Abvorn".

Site homepage `{slug}/index.html` lists all published posts for that site.

- [ ] **Step 4: Run tests to verify**

- [ ] **Step 5: Commit**

---

### Task 11: Daemon Wiring + Bootstrap Migration

**Files:**
- Modify: `abvorn/daemon.py` (wire SiteRegistry, BootstrapMigration)
- Modify: `abvorn/__main__.py` (add `migrate` command)
- Create: `abvorn/sites/migration.py`

- [ ] **Step 1: Write `abvorn/sites/migration.py`**

Bootstrap creates "Tech & Gadgets" site if no sites exist. Assigns all existing niches to it. Writes redirect HTML at old `docs/{niche}/` paths.

- [ ] **Step 2: Wire into `AbvornDaemon._init_phase3()`**

Initialize `SiteRegistry`, `SiteAwareDeployer`, `CrossLinker`. Wire into notifier.

- [ ] **Step 3: Run bootstrap migration**

Run `python -m abvorn migrate` to create the initial site + redirects.

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short
```
Expected: All tests pass

- [ ] **Step 5: Commit**

---

### Task 12: Update Roadmap

**Files:**
- Modify: `abvorn/brain/roadmap.md`

- [ ] **Step 1: Move "Autonomous Affiliate Network" from Tier 3 to Tier 1 (Active Build)**

Add module path, classes, test count.

- [ ] **Step 2: Commit**

```bash
git commit -m "docs: update roadmap — Autonomous Affiliate Network to Tier 1"
```
