# Real-Time Persuasion Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Embed a context-aware product recommendation assistant on every blog post. Knows article niche, persona, and buying stage. Zero server cost (fully static).

**Architecture:** Hybrid — deploy-time context analysis + runtime JS rendering from embedded JSON. No backend needed.

**Tech Stack:** Python 3.14, SQLite (AbvornState), GitHub Pages (static deploy)

## Global Constraints

- All state stored in existing SQLite via `AbvornState` — no new databases or external services
- Widget must be self-contained (inline CSS + JS) — no external CDN deps
- Widget must not break if JS is disabled (graceful fallback to static HTML)
- ProductMatcher LLM fallback must cache results per niche+stage to avoid regenerating every deploy
- Click tracking via beacon only — best-effort, non-blocking
- All tests must use mocked state, no real API calls
- Track cumulative test count

---

### Task 1: BuyingStageDetector + Enum + Tests

**Files:**
- Create: `abvorn/persuasion/__init__.py`
- Create: `abvorn/persuasion/stage.py`
- Create: `tests/persuasion_stage_test.py`

**Interfaces:**
- `BuyingStage` enum: `AWARENESS`, `CONSIDERATION`, `DECISION`
- `detect_stage(content: dict) -> BuyingStage` — keyword scoring function

**Test:**
```python
"""Tests for BuyingStageDetector."""
import pytest
from abvorn.persuasion.stage import BuyingStage, detect_stage


def test_awareness_from_title():
    content = {"title": "What is 4K TV? A Complete Guide", "article_html": "<p>4K TVs have four times the pixels...</p>"}
    assert detect_stage(content) == BuyingStage.AWARENESS


def test_consideration_from_title():
    content = {"title": "Best Wireless Headphones of 2026", "article_html": "<p>We tested 20 pairs...</p>"}
    assert detect_stage(content) == BuyingStage.CONSIDERATION


def test_decision_from_title():
    content = {"title": "Buy Samsung QN90A — Best Price Today", "article_html": "<p>Where to buy the QN90A...</p>"}
    assert detect_stage(content) == BuyingStage.DECISION


def test_awareness_from_content():
    content = {"title": "TV Technology Explained", "article_html": "<p>A guide to understanding different types of TV panels...</p>"}
    assert detect_stage(content) == BuyingStage.AWARENESS


def test_consideration_from_content():
    content = {"title": "Top Rated Monitors", "article_html": "<p>Comparison of the top 10 monitors for 2026...</p>"}
    assert detect_stage(content) == BuyingStage.CONSIDERATION


def test_decision_from_content():
    content = {"title": "Monitor Discounts", "article_html": "<p>Best price on the LG UltraGear — save $200 today...</p>"}
    assert detect_stage(content) == BuyingStage.DECISION


def test_empty_content_defaults_to_awareness():
    content = {"title": "", "article_html": ""}
    assert detect_stage(content) == BuyingStage.AWARENESS
```

**Implementation:**
```python
"""BuyingStageDetector — classifies articles into buying stages."""

from enum import Enum


class BuyingStage(Enum):
    AWARENESS = "awareness"
    CONSIDERATION = "consideration"
    DECISION = "decision"


STAGE_KEYWORDS = {
    BuyingStage.AWARENESS: [
        "what is", "guide to", "types of", "how to choose", "introduction",
        "explained", "understanding", "beginner's guide", "overview",
    ],
    BuyingStage.CONSIDERATION: [
        "best", "top", "review", "vs", "comparison", "versus",
        "compared", "rated", "recommended", "ranking",
    ],
    BuyingStage.DECISION: [
        "buy", "discount", "coupon", "price", "where to buy",
        "affordable", "deals", "save", "cheap", "order",
    ],
}


def detect_stage(content: dict) -> BuyingStage:
    title = (content.get("title") or "").lower()
    body = (content.get("article_html") or "")[:500].lower()

    text = f"{title} {body}"

    if not text.strip():
        return BuyingStage.AWARENESS

    scores = {stage: 0 for stage in BuyingStage}
    for stage, keywords in STAGE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[stage] += 1

    max_stage = max(scores, key=scores.get)
    return max_stage if scores[max_stage] > 0 else BuyingStage.AWARENESS
```

**Steps:** TDD — write test, fail, implement, pass, commit.

**Commit msg:** `feat: BuyingStageDetector with keyword scoring`

---

### Task 2: ContextParser + Tests

**Files:**
- Create: `abvorn/persuasion/context.py`
- Create: `tests/persuasion_context_test.py`

**Interfaces:**
- `PersuasionContext` dataclass: niche, persona_name, buying_stage, keywords (list[str]), product_intents (list[str])
- `ContextParser.parse(content: dict, persona: dict | None) -> PersuasionContext`

**Test:**
```python
"""Tests for ContextParser."""
from abvorn.persuasion.context import ContextParser, PersuasionContext
from abvorn.persuasion.stage import BuyingStage


def test_parse_returns_context_with_keywords():
    parser = ContextParser()
    content = {"title": "Best Noise Cancelling Headphones", "article_html": "<p>Top 10 noise cancelling headphones reviewed...</p>", "niche": "headphones"}
    persona = {"name": "Alex", "traits": ["tech-savvy", "audio-lover"]}
    ctx = parser.parse(content, persona)
    assert isinstance(ctx, PersuasionContext)
    assert ctx.niche == "headphones"
    assert ctx.persona_name == "Alex"
    assert ctx.buying_stage == BuyingStage.CONSIDERATION
    assert len(ctx.keywords) > 0


def test_parse_without_persona():
    parser = ContextParser()
    content = {"title": "Buy Cheap Monitors", "article_html": "<p>Where to find monitor deals...</p>", "niche": "monitor"}
    ctx = parser.parse(content, None)
    assert ctx.persona_name == ""
    assert ctx.buying_stage == BuyingStage.DECISION
```

**Implementation:**
```python
"""ContextParser — extracts persuasion context from content + persona."""

import re
from dataclasses import dataclass, field
from .stage import BuyingStage, detect_stage


@dataclass
class PersuasionContext:
    niche: str
    persona_name: str
    buying_stage: BuyingStage
    keywords: list[str] = field(default_factory=list)
    product_intents: list[str] = field(default_factory=list)


class ContextParser:
    """Analyzes article content to produce PersuasionContext."""

    def parse(self, content: dict, persona: dict | None = None) -> PersuasionContext:
        niche = content.get("niche", "") or ""
        persona_name = (persona or {}).get("name", "") or ""
        buying_stage = detect_stage(content)

        text = f"{content.get('title', '')} {content.get('article_html', '')}".lower()
        keywords = self._extract_keywords(text)
        product_intents = self._extract_intents(text)

        return PersuasionContext(
            niche=niche,
            persona_name=persona_name,
            buying_stage=buying_stage,
            keywords=keywords,
            product_intents=product_intents,
        )

    def _extract_keywords(self, text: str, max_keywords: int = 5) -> list[str]:
        words = re.findall(r'\b[a-z]{4,}\b', text)
        stopwords = {"this", "that", "with", "from", "have", "been", "were", "they", "their", "what", "which", "where", "when", "about", "above", "after", "again", "than", "them", "then", "there", "these", "thing", "very", "just", "also", "more", "some", "into", "over", "such", "only", "other", "each", "could", "would", "should"}
        words = [w for w in words if w not in stopwords]
        freq = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: -x[1])
        return [w for w, _ in sorted_words[:max_keywords]]

    def _extract_intents(self, text: str) -> list[str]:
        patterns = [
            r'(?:best|top|cheap|affordable|buy|review)\s+([a-z\s]{3,30}?)',
            r'([a-z\s]{3,30}?)\s+(?:review|comparison|vs\.?)',
        ]
        intents = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for m in matches:
                cleaned = m.strip()[:40]
                if cleaned and cleaned not in intents:
                    intents.append(cleaned)
        return intents[:3]
```

**Steps:** TDD — write test, fail, implement, pass, commit.

**Commit msg:** `feat: ContextParser with keyword and intent extraction`

---

### Task 3: ProductMatcher + Tests

**Files:**
- Create: `abvorn/persuasion/matcher.py`
- Create: `tests/persuasion_matcher_test.py`

**Interfaces:**
- `ProductRecommendation` dataclass: name, tagline, price_range, affiliate_url, reason_to_buy
- `ProductMatcher.match(context: PersuasionContext) -> list[ProductRecommendation]` — up to 3

**Test:**
```python
"""Tests for ProductMatcher."""
from unittest.mock import MagicMock
from abvorn.persuasion.matcher import ProductMatcher, ProductRecommendation
from abvorn.persuasion.context import PersuasionContext
from abvorn.persuasion.stage import BuyingStage


def test_match_returns_products_from_catalog():
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"name":"Sony WH-1000XM5","tagline":"Best noise cancelling",'
        '"price_range":"$299-$349","affiliate_url":"https://amzn.to/sony",'
        '"reason_to_buy":"Industry-leading ANC"}]'
    )
    matcher = ProductMatcher(state)
    ctx = PersuasionContext(niche="headphones", persona_name="Alex",
                            buying_stage=BuyingStage.CONSIDERATION,
                            keywords=["noise", "cancelling"], product_intents=["headphones"])
    results = matcher.match(ctx)
    assert len(results) > 0
    assert results[0].name == "Sony WH-1000XM5"


def test_match_handles_empty_catalog():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    matcher = ProductMatcher(state)
    ctx = PersuasionContext(niche="unknown", persona_name="", buying_stage=BuyingStage.AWARENESS)
    results = matcher.match(ctx)
    assert len(results) == 0


def test_match_up_to_three():
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"name":"A","tagline":"a","price_range":"$10","affiliate_url":"https://a.com","reason_to_buy":"good"},'
        '{"name":"B","tagline":"b","price_range":"$20","affiliate_url":"https://b.com","reason_to_buy":"better"},'
        '{"name":"C","tagline":"c","price_range":"$30","affiliate_url":"https://c.com","reason_to_buy":"best"},'
        '{"name":"D","tagline":"d","price_range":"$40","affiliate_url":"https://d.com","reason_to_buy":"extra"}]'
    )
    matcher = ProductMatcher(state)
    ctx = PersuasionContext(niche="tv", persona_name="", buying_stage=BuyingStage.CONSIDERATION)
    results = matcher.match(ctx)
    assert len(results) <= 3
```

**Implementation:**
```python
"""ProductMatcher — matches products to persuasion context."""

import json
import logging
from dataclasses import dataclass, field
from ..sites.model import BrandConfig

logger = logging.getLogger("abvorn.persuasion.matcher")
MAX_PRODUCTS = 3
PRODUCTS_KEY = "persuasion:products"


@dataclass
class ProductRecommendation:
    name: str
    tagline: str
    price_range: str
    affiliate_url: str
    reason_to_buy: str = ""
    image_url: str = ""


class ProductMatcher:
    """Matches products from catalog to context. Falls back to empty list."""

    def __init__(self, state):
        self._state = state

    def match(self, context) -> list[ProductRecommendation]:
        products = self._load_products(context.niche)
        products = self._rank_by_stage(products, context.buying_stage)
        return products[:MAX_PRODUCTS]

    def _load_products(self, niche: str) -> list[ProductRecommendation]:
        raw = self._state.get_meta(f"{PRODUCTS_KEY}:{niche}", "[]")
        data = json.loads(raw) if isinstance(raw, str) else raw
        result = []
        for item in data:
            result.append(ProductRecommendation(
                name=item.get("name", ""),
                tagline=item.get("tagline", ""),
                price_range=item.get("price_range", ""),
                affiliate_url=item.get("affiliate_url", ""),
                reason_to_buy=item.get("reason_to_buy", ""),
                image_url=item.get("image_url", ""),
            ))
        return result

    def _rank_by_stage(self, products: list, stage) -> list:
        if stage.value == "decision":
            return sorted(products, key=lambda p: self._price_value(p), reverse=True)
        elif stage.value == "awareness":
            return sorted(products, key=lambda p: self._price_value(p))
        return products

    def _price_value(self, p: ProductRecommendation) -> float:
        import re
        nums = re.findall(r'\d+', p.price_range)
        return int(nums[0]) if nums else 0
```

**Steps:** TDD

**Commit msg:** `feat: ProductMatcher with catalog-based matching`

---

### Task 4: PersuasionWidget HTML+JS Generator + Tests

**Files:**
- Create: `abvorn/persuasion/widget.py`
- Create: `tests/persuasion_widget_test.py`

**Interfaces:**
- `PersuasionWidget.render(context, recommendations, brand) -> str` — returns HTML+JS snippet

**Test:**
```python
"""Tests for PersuasionWidget."""
from abvorn.persuasion.widget import PersuasionWidget
from abvorn.persuasion.context import PersuasionContext
from abvorn.persuasion.matcher import ProductRecommendation
from abvorn.persuasion.stage import BuyingStage


def test_widget_renders_html():
    widget = PersuasionWidget()
    ctx = PersuasionContext(niche="headphones", persona_name="", buying_stage=BuyingStage.CONSIDERATION)
    recs = [
        ProductRecommendation(name="Sony WH-1000XM5", tagline="Best ANC", price_range="$349",
                              affiliate_url="https://amzn.to/sony", reason_to_buy="Quietest on market")
    ]
    html = widget.render(ctx, recs)
    assert "Sony" in html
    assert "$349" in html
    assert "amzn.to" in html
    assert "persuasion" in html.lower()


def test_widget_empty_recommendations():
    widget = PersuasionWidget()
    ctx = PersuasionContext(niche="tv", persona_name="", buying_stage=BuyingStage.AWARENESS)
    html = widget.render(ctx, [])
    assert html == ""  # no recommendations → no widget


def test_widget_includes_json_data():
    widget = PersuasionWidget()
    ctx = PersuasionContext(niche="tv", persona_name="Alex", buying_stage=BuyingStage.DECISION)
    recs = [ProductRecommendation(name="LG C3", tagline="OLED", price_range="$1500",
                                  affiliate_url="https://amzn.to/lg", reason_to_buy="Best OLED")]
    html = widget.render(ctx, recs)
    assert "__ABVORN_PERSUASION" in html
    assert "LG C3" in html
```

**Implementation:**
```python
"""PersuasionWidget — generates embeddable HTML+JS product recommendation widget."""

import json
from html import escape


class PersuasionWidget:
    """Generates self-contained HTML+JS widget for product recommendations."""

    def render(self, context, recommendations: list, brand=None) -> str:
        if not recommendations:
            return ""

        data = {
            "niche": context.niche,
            "persona": context.persona_name,
            "stage": context.buying_stage.value,
            "products": [
                {
                    "name": r.name,
                    "tagline": r.tagline,
                    "price": r.price_range,
                    "url": r.affiliate_url,
                    "reason": r.reason_to_buy,
                    "image": r.image_url,
                }
                for r in recommendations
            ],
        }
        json_data = escape(json.dumps(data), quote=False)

        cards = ""
        for i, r in enumerate(recommendations):
            price_html = f'<span class="pr-price">{escape(r.price_range)}</span>' if r.price_range else ""
            reason_html = f'<p class="pr-reason">{escape(r.reason_to_buy)}</p>' if r.reason_to_buy else ""
            cards += f"""
<div class="pr-card" data-index="{i}">
  <a href="{escape(r.affiliate_url)}" target="_blank" rel="sponsored noopener" data-persuasion-click="{i}">
    <strong>{escape(r.name)}</strong>
    {price_html}
  </a>
  <p class="pr-tagline">{escape(r.tagline)}</p>
  {reason_html}
</div>"""

        return f"""<div id="abvorn-persuasion" class="abvorn-persuasion">
<style>
.abvorn-persuasion{{margin:24px 0;padding:16px;border:1px solid #e0e0e0;border-radius:8px;background:#fafafa;font-family:-apple-system,sans-serif;}}
.abvorn-persuasion h3{{margin:0 0 12px;font-size:16px;color:#333;}}
.pr-card{{padding:8px 0;border-bottom:1px solid #eee;}}
.pr-card:last-child{{border-bottom:none;}}
.pr-card a{{text-decoration:none;color:#1a73e8;font-size:15px;display:block;}}
.pr-card a:hover{{text-decoration:underline;}}
.pr-price{{font-size:13px;color:#666;margin-left:4px;}}
.pr-tagline{{margin:2px 0 0;font-size:13px;color:#555;}}
.pr-reason{{margin:2px 0 0;font-size:12px;color:#888;font-style:italic;}}
</style>
<h3>Recommended for you</h3>
<div class="pr-cards">{cards}</div>
<script>
(function(){{
  var w=window;
  if(w.__ABVORN_PERSUASION_INITED)return;
  w.__ABVORN_PERSUASION_INITED=true;
  var data={json_data};
  var clicks=document.querySelectorAll('[data-persuasion-click]');
  for(var i=0;i<clicks.length;i++){{
    clicks[i].addEventListener('click',function(e){{
      var idx=this.getAttribute('data-persuasion-click');
      if(navigator.sendBeacon){{
        navigator.sendBeacon('/api/persuasion/click','idx='+idx+'&niche='+data.niche+'&stage='+data.stage);
      }}
    }});
  }}
}})();
</script>
</div>"""
```

**Steps:** TDD

**Commit msg:** `feat: PersuasionWidget with self-contained HTML+JS`

---

### Task 5: Wire into GitHubDeployer + Tests

**Files:**
- Modify: `abvorn/deploy/github.py` (inject widget into `prepare_files()`)
- Modify: `tests/deploy_test.py` (append test)

Wire the widget into the deploy pipeline: after rendering the page, inject the persuasion widget HTML before `</article>`.

**Test:**
```python
def test_page_includes_persuasion_when_brand_provided():
    from pathlib import Path
    import tempfile
    from abvorn.sites.model import BrandConfig, DNAProfile
    deployer = GitHubDeployer(token="fake", repo="user/repo")
    brand = BrandConfig(brand_name="Test", brand_tagline="", logo_text="T", logo_icon="T",
                        primary_color="#000", secondary_color="#fff",
                        dna_profile=DNAProfile.TECH, voice_rules={}, domain="")
    content = {"post_title": "Best TVs", "article_html": "<p>Content</p>", "niche_slug": "best-tvs",
               "niche": "tv"}
    with tempfile.TemporaryDirectory() as tmpdir:
        files = deployer.prepare_files(content, Path(tmpdir), brand=brand)
        html = Path(files[0]).read_text(encoding="utf-8")
        assert "abvorn-persuasion" in html
```

**Implementation detail:**
In `GitHubDeployer.prepare_files()`, after building `full_html`, if brand is provided:
1. Create ContextParser → parse(content + optional persona from brand.voice_rules)
2. Create ProductMatcher → match(context)
3. Create PersuasionWidget → render_html = widget.render(context, recommendations, brand)
4. Inject render_html before `</article>` in full_html

**Steps:** TDD

**Commit msg:** `feat: wire persuasion widget into deploy pipeline`

---

### Task 6: ClickTracker + Tests

**Files:**
- Create: `abvorn/persuasion/tracker.py`
- Create: `tests/persuasion_tracker_test.py`

**Interfaces:**
- `ClickTracker.record_click(niche: str, stage: str, product_index: int)` — stores click in state DB
- `ClickTracker.record_impression(niche: str, stage: str)` — stores impression in state DB
- `ClickTracker.get_stats(niche: str | None = None) -> dict` — returns click/impression stats

**Test:**
```python
"""Tests for ClickTracker."""
from unittest.mock import MagicMock
from abvorn.persuasion.tracker import ClickTracker


def test_record_click_stores():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    tracker = ClickTracker(state)
    tracker.record_click("tv", "consideration", 0)
    assert state.set_meta.called


def test_record_impression_stores():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    tracker = ClickTracker(state)
    tracker.record_impression("tv", "awareness")
    assert state.set_meta.called


def test_get_stats_empty():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    tracker = ClickTracker(state)
    stats = tracker.get_stats()
    assert "total_clicks" in stats
    assert stats["total_clicks"] == 0
```

**Implementation:**
```python
"""ClickTracker — records widget clicks and impressions in state DB."""

import json
import logging
from datetime import datetime

logger = logging.getLogger("abvorn.persuasion.tracker")
STORAGE_KEY = "persuasion:events"


class ClickTracker:
    """Tracks persuasion widget clicks and impressions."""

    def __init__(self, state):
        self._state = state

    def record_click(self, niche: str, stage: str, product_index: int):
        self._append_event({
            "type": "click",
            "niche": niche,
            "stage": stage,
            "product_index": product_index,
            "timestamp": datetime.now().isoformat(),
        })

    def record_impression(self, niche: str, stage: str):
        self._append_event({
            "type": "impression",
            "niche": niche,
            "stage": stage,
            "timestamp": datetime.now().isoformat(),
        })

    def get_stats(self, niche: str = None) -> dict:
        raw = self._state.get_meta(STORAGE_KEY, "[]")
        events = json.loads(raw) if isinstance(raw, str) else raw
        if niche:
            events = [e for e in events if e.get("niche") == niche]
        clicks = [e for e in events if e.get("type") == "click"]
        impressions = [e for e in events if e.get("type") == "impression"]
        return {
            "total_clicks": len(clicks),
            "total_impressions": len(impressions),
            "click_rate": len(clicks) / len(impressions) if impressions else 0.0,
        }

    def _append_event(self, event: dict):
        raw = self._state.get_meta(STORAGE_KEY, "[]")
        events = json.loads(raw) if isinstance(raw, str) else raw
        events.append(event)
        self._state.set_meta(STORAGE_KEY, json.dumps(events, default=str))
```

**Steps:** TDD

**Commit msg:** `feat: ClickTracker for persuasion widget analytics`

---

### Task 7: Full Test Suite + Commit

Run: `python -m pytest tests/persuasion_* tests/ -v --tb=short`
All tests must pass. Verify no pre-existing tests broken.

**Commit msg:** `chore: verify full test suite after persuasion layer`
