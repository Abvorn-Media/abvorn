# Real-Time Persuasion Layer — Design Spec

## Vision

Every Abvorn-published blog post carries an embedded assistant that reads the article context, knows the reader's buying stage, and recommends the right affiliate product at the right time. Zero server cost (fully static). Converts traffic competitors can't.

## Architecture

### Hybrid Static + Runtime

- **At deploy time:** Context is analyzed (buying stage, persona, niche), product recommendations are computed, and a self-contained HTML+JS widget with embedded JSON data is injected into the page.
- **At runtime (browser):** JavaScript reads the embedded JSON, detects buying stage from URL patterns or scroll depth, renders ranked product cards, and fires click beacons.

No backend server needed. Works on GitHub Pages.

## Core Components

### 1. BuyingStageDetector (`abvorn/persuasion/stage.py`)
Heuristic + keyword engine that classifies article content into one of three buying stages:

- **AWARENESS** — "what is", "guide to", "types of", "how to choose"
- **CONSIDERATION** — "vs", "comparison", "review of", "top 10", "best"
- **DECISION** — "buy", "discount", "coupon", "price", "where to buy", "affordable"

**Input:** Content dict (title, article_html, niche)
**Output:** `BuyingStage` enum (AWARENESS / CONSIDERATION / DECISION)

**Method:** Keyword scoring against title + first 500 chars of article. Highest score wins.

### 2. ContextParser (`abvorn/persuasion/context.py`)
Wraps BuyingStageDetector + extracts additional context signals:

- **Input:** Content dict, persona dict
- **Output:** `PersuasionContext` dataclass containing: niche, persona_name, buying_stage, keywords (top 5 extracted), product_intents

Product intents extracted from article: e.g., "noise-cancelling headphones" → intent: headphones with noise-cancelling feature.

### 3. ProductMatcher (`abvorn/persuasion/matcher.py`)
Matches products to context. Two modes:

- **Catalog mode:** Queries existing product data from state DB (products per niche, with features and affiliate links)
- **LLM mode (fallback):** Uses ModelRouter to generate plausible product recommendations with placeholder affiliate links when no catalog data exists

**Input:** PersuasionContext
**Output:** List of `ProductRecommendation` (name, tagline, price_range, affiliate_url, image_url, reason_to_buy)

Returns up to 3 recommendations, ranked by relevance to buying stage:
- AWARENESS → educational/guide-style products, lowest price point
- CONSIDERATION → comparison products, mid range
- DECISION → specific buy recommendations, highest commission potential

### 4. PersuasionWidget (`abvorn/persuasion/widget.py`)
Generates the HTML+JS snippet to be embedded in every page.

**Deploy-time:**
- Takes `PersuasionContext` + list of `ProductRecommendation`
- Generates a `<div id="abvorn-persuasion">` containing:
  - A `<script>` tag with JSON data: `window.__ABVORN_PERSUASION = {...}`
  - CSS for the widget (inline, self-contained, no external deps)
  - HTML structure for product cards
  - JS that renders cards from JSON, handles click tracking

**Runtime JS behavior:**
- On page load: render product cards from embedded JSON
- Buying stage override: URL param `?stage=decision` overrides detected stage
- Click tracking: `navigator.sendBeacon()` to a lightweight endpoint (GA4 event or pixel)
- Collapsed by default on mobile, expands on interaction

### 5. ClickTracker (`abvorn/persuasion/tracker.py`)
Records widget clicks and impressions.

- **Impressions:** Counted when widget renders (via IntersectionObserver in JS + beacon)
- **Clicks:** Each product link has `data-persuasion-click` attribute; JS captures clicks, fires beacon
- **Storage:** State DB meta key `persuasion:clicks` + `persuasion:impressions`

## Data Flow

```
Content Pipeline
      │
      ▼
ContextParser.parse(content, persona)
      │
      ▼
ProductMatcher.match(context)
      │
      ▼
PersuasionWidget.render(context, recommendations)
      │
      ▼
GitHubDeployer.prepare_files() ── injects widget HTML
      │
      ▼
Static page deployed with embedded widget
      │
      ▼
Browser ── JS reads JSON → renders cards → tracks clicks
```

## File Plan

```
abvorn/persuasion/
  __init__.py
  stage.py         — BuyingStageDetector + BuyingStage enum
  context.py       — PersuasionContext dataclass + ContextParser
  matcher.py       — ProductRecommendation dataclass + ProductMatcher
  widget.py        — PersuasionWidget (HTML+JS generator)
  tracker.py       — ClickTracker (impression + click recording)

tests/
  persuasion_stage_test.py
  persuasion_context_test.py
  persuasion_matcher_test.py
  persuasion_widget_test.py
  persuasion_tracker_test.py
```

## Non-Goals

- No real-time personalization per visitor (static site limitation)
- No user authentication or profile tracking
- No server-side click processing (beacon-only, best-effort)
- No A/B testing of widget variants (future)

## Open Questions

- Product catalog schema: needs product data in state DB with affiliate links, features, price ranges
- LLM generation cost: ProductMatcher LLM fallback should cache results to avoid regenerating on every deploy
- Beacon endpoint: For now, GA4 events via existing GA4Client. Future: a lightweight pixel collector.
