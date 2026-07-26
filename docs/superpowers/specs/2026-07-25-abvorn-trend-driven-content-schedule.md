# Trend-Driven Content Schedule

> Automated pipeline: scan what's hot → plan content → post 2x daily.
> Living schedule with trend injection + evergreen fallback.

## Architecture

`abvorn/trends/` module with three components and integration into the existing daemon cycle.

```
TrendScanner ──→ ContentPlanner ──→ Schedule ──→ Composio
     ↑                                    │
  [web, Amazon,                       [evergreen
   Google Trends]                      fallback]
```

## Components

### 1. TrendScanner (`abvorn/trends/scanner.py`)

Polls 3 sources for trending tech products:

- **Web search** — uses web search API to query "best [category] 2026" for 5-10 tech subcategories (TVs, robot vacuums, laptops, monitors, headphones, smart home, etc.). Extracts product names, prices, and frequency of mention from top results using regex + NLP heuristics.
- **Amazon Bestsellers** — fetches Amazon product data via affiliate API or structured search results. Tracks top sellers, new releases, and movers & shakers in Electronics and Smart Home categories.
- **Google Trends** — queries daily trending tech searches via the pytrends Python library. Tracks rising queries and breakout terms in the Technology category.

Each source returns `[{product_name, category, price_range, source, score, url}]` with scores normalized 0-100. Products appearing in 2+ sources get a combined score boost.

Configurable: `min_score` threshold, scrape interval (default 6h), result cache (24h dedup). Start with 5 tech subcategories: TVs, robot vacuums, laptops, monitors, and smart home devices. Expandable via config.

### 2. ContentPlanner (`abvorn/trends/planner.py`)

Takes scored trends from TrendScanner, picks the top product above threshold, consults Intel engine for best content type:

| Type | Output | Primary Platform | Secondary |
|------|--------|-----------------|-----------|
| buying_guide | Full blog post with CTAs | Blog | LinkedIn |
| comparison | X vs Y comparison | Blog | LinkedIn |
| social_thread | Multi-post thread | X | TikTok/IG |
| tiktok_script | Short-form script | TikTok | Instagram |

Intent mapping: high-intent products → deep content (blog). Low-intent / viral trends → light content (social).

### 3. Schedule (`abvorn/trends/schedule.py`)

Fixed 2-slot daily rhythm:

| Slot | Time | Content Type | Primary | Secondary |
|------|------|-------------|---------|-----------|
| AM | 08:00 | Deep (guide/comparison) | Blog | LinkedIn |
| PM | 16:00 | Light (thread/hook) | X | TikTok, Instagram |

Queue-based: planner fills queue → schedule pops at slot time → blog posts directly, social posts via Composio adapter (stubs gracefully when Composio not connected) → records metadata.

Fallback: if queue is empty at slot time, pulls from evergreen rotation — pre-defined list of staple tech categories (TVs, robot vacuums, laptops, monitors, headphones) on a 5-day rotating cycle.

## Integration

- Posts get CTA-injected via `abvorn/cta/` + hook-optimized via `abvorn/hooks/` + UIX-embedded via `abvorn/uix/`
- Daemon (`abvorn/daemon.py`) tracks post performance and feeds back into trend scoring
- Living Archive marks posts for auto-refresh when product data changes
- Composio handles all social posting (never direct API)

## Implementation

1. Create `abvorn/trends/` package with `__init__.py`
2. Implement `scanner.py` — TrendScanner with web, Amazon, Google Trends sources
3. Implement `planner.py` — ContentPlanner with intent mapping
4. Implement `schedule.py` — Schedule with queue + evergreen fallback
5. Wire into daemon cycle (daemon runs TrendScanner every 6h)
6. Create `tests/trends_test.py` — unit tests for all components