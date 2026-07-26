# Predictive Trend Detection — Design Spec

## Goal
Detect rising products before they peak by tracking signal velocity across DuckDuckGo, Amazon, Reddit, and Google Trends. Boost TrendScanner scores for products showing acceleration.

## Architecture
Module: `abvorn/trends/predict/` (~200 lines)

### Components

#### 1. SignalSnapshotter
Stores which products appeared per niche per source per scan cycle.

**State DB keys:** `trend_signal:{niche}:{source}`  
**Value:** JSON list of snapshots — `[{"ts": ISO timestamp, "products": [name, ...], "count": int}, ...]`

Keeps last 50 snapshots per key. Purges oldest on each write.  
Called at end of `TrendScanner.scan()` per niche, after providers return results.

#### 2. VelocityTracker
On each scan, compares latest snapshot against prior N (default 5) for same niche+source.

Computes per product:
- **Frequency** — in how many of the last N snapshots did this product appear?
- **Source breadth** — across how many different sources was this product found?
- **New entrant** — first appearance in the most recent snapshot

#### 3. ScoreBooster
Plugs into TrendScanner's `_combine_results()`. Adjusts product scores:
- +10 if seen in 2+ prior snapshots, +20 if 4+
- +15 if appearing across 2+ different sources
- +5 if newly appeared (novelty)
- Capped at +30 total boost per product

### Data Flow
```
TrendScanner.scan()
  → providers.search(category) per niche
  → SignalSnapshotter.store(niche, results)       # NEW
  → _combine_results()
      → ScoreBooster.boost(products, niche)       # NEW
  → return boosted results
```

### Error Handling
- Snapshotter wrapped in try/except — failure doesn't block scan
- Booster degrades: missing velocity data = no boost applied
- Nothing blocks content production

### Telegram Integration
New `/predict [niche]` command in notifier.py:
- Shows top 3 rising products for that niche
- Indicators: 🔥 accelerating, ↑ rising, ● stable

### Testing
3 tests:
- Snapshotter stores and retrieves correctly
- Velocity tracker computes frequency
- Booster doesn't boost unknown products

All use mocked state. No real API calls.

## Files

**Create:**
- `abvorn/trends/predict/__init__.py` — empty
- `abvorn/trends/predict/snapshotter.py` — SignalSnapshotter
- `abvorn/trends/predict/velocity.py` — VelocityTracker
- `abvorn/trends/predict/booster.py` — ScoreBooster
- `tests/predict_test.py` — 3 tests

**Modify:**
- `abvorn/trends/scanner.py` — wire snapshotter + booster into scan()
- `abvorn/deploy/notifier.py` — add `/predict` command
- `abvorn/brain/roadmap.md` — move predictive trend detection to Tier 1