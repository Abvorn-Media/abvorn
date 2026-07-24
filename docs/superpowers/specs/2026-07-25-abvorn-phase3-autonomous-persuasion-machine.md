# Abvorn Phase 3 — The Autonomous Persuasion Machine

> **Date:** 2026-07-25
> **Status:** Draft — awaiting user review
> **Vision:** A 24/7 autonomous content machine that discovers opportunities, writes for specific human personas, publishes across 8 channels, captures emails, converts through affiliate sales + AdSense, and gets smarter with every cycle.

---

## 1. System Architecture

### 1.1 Overview

Seven subsystems operating in a continuous loop:

```
DISCOVERY → PERSONA → FACTORY → EXPLODE → DEPLOY → ANALYZE → LEARN → (loop)
                                            ↕
                                        EMAIL CRM
```

Each cycle targets one niche + one persona → produces one anchor asset → derives 8 platform-native outputs + AdSense blog + email sequence → captures performance data → feeds back into the brain.

### 1.2 Revenue Model (three streams from one post)

| Stream | Source | Primary |
|--------|--------|---------|
| Affiliate commissions | Product links in content | Primary |
| AdSense | Display ads on blog pages | Secondary |
| Email nurture | Lead magnet → sequence → future conversions | Tertiary |

---

## 2. Subsystem 1: Opportunity Discovery

### 2.1 Purpose
Continuously scan for untapped affiliate opportunities. Feed the queue with scored opportunities.

### 2.2 Data Sources
- **Keyword research** — buying-intent keywords via SEO APIs, trend data
- **Affiliate networks** — commission rates, product availability, program strength
- **Competitor monitoring** — detect when competitors publish, identify content gaps
- **Trend detection** — rising search volume before it peaks

### 2.3 Scoring Formula
```
Opportunity Score = Search Demand × Buying Intent × Commission Value ÷ Competition
```
Each factor normalized 0-1, producing a 0-1 score.

### 2.4 File: `abvorn/discovery/scanner.py`
- `scan_market() → list[Opportunity]` — full market scan
- `score_opportunity(niche) → float` — single niche score

### 2.5 File: `abvorn/discovery/__init__.py`
- Package exports

---

## 3. Subsystem 2: Persona Engine

### 3.1 Purpose
Maintain a living registry of buyer personas. For each niche, identify the ideal persona. Each post targets exactly one persona. Personas evolve with performance data.

### 3.2 Persona Data Model

```python
Persona {
  id: str, niche: str
  name: str  # e.g. "Marcus the Commuter"
  demographics: { age, job, income, location, family_status }
  psychology: {
    awareness_level: unaware | problem_aware | solution_aware | product_aware | most_aware
    primary_lf8_desire: which Life-Force 8 desire
    cialdini_principles: [reciprocity, scarcity, authority, etc.]
    hoffeld_buying_reason: gain | avoid | feel | conform | identity | reduce_uncertainty
    anxieties: [str]
    hopes: [str]
    daily_obstacles: [str]
  }
  performance: { posts, clicks, conversions, total_revenue, winning_angles, retired }
  status: active | promising | retired
}
```

### 3.3 Persona Discovery
For each niche, derive 2-5 candidate personas by analyzing:
- Search intent data (who searches for this?)
- Existing content gaps (who is underserved?)
- Brain psychology frameworks (which desires apply?)

### 3.4 File: `abvorn/persona/engine.py`
- `discover_personas(niche) → list[Persona]` — derive personas for a niche
- `select_persona(personas) → Persona` — pick the best for this cycle
- `update_performance(persona_id, result) → None` — feed back analytics

### 3.5 File: `abvorn/persona/registry.py`
- `PersonaRegistry` — SQLite-backed persona storage (extends `AbvornState`)
- Autoretire: if a persona has 5+ posts with <1% conversion rate, mark as retired

### 3.6 File: `abvorn/persona/__init__.py`
- Package exports

---

## 4. Subsystem 3: Content Factory

### 4.1 Purpose
Produce one anchor asset per cycle using the brain's persuasion frameworks, targeted at exactly one persona.

### 4.2 The Persuasion Pipeline (from brain frameworks)

| Stage | Framework | What it does |
|-------|-----------|--------------|
| 1. Pre-suade | Cialdini | Frame context, establish trust cues before pitch |
| 2. Awareness match | Schwartz | Lead at their awareness level. Don't explain what they already know |
| 3. Tap desire | Whitman LF8 | Activate the right Life-Force 8 desire for THIS persona |
| 4. Neuro engage | Lindstrom | Mirror neuron language. Sensory-rich. Let them *feel* it |
| 5. Evidence + objections | Hoffeld | Progressive commitments. Address objections before they're raised |
| 6. Scannable structure | Krug | F-pattern, billboard design, no thinking required |
| 7. Convert | Ash + Pribyl | One CTA. Trust signals. Accurate affiliate link to buying page |
| 8. Lead magnet | Email CRM | Valuable asset → email capture |

### 4.3 Content Types (selected per niche/persona)
- Buying guide ("Best X for [persona need]")
- Comparison ("X vs Y — which wins?")
- Review ("X review after 30 days")
- Listicle ("5 reasons X is the best")
- Problem/solution ("Tired of [pain]? Here's the fix")

### 4.4 File: `abvorn/factory/pipeline.py`
- `run(niche, persona, brain) → dict` — full content generation cycle
- Returns: title, article_html, meta_description, lead_magnet, tags, schema

### 4.5 File: `abvorn/factory/persuasion.py`
- Contains the persuasion pipeline steps as modular prompt builders
- Each step queries the brain for relevant framework guidance

### 4.6 File: `abvorn/factory/__init__.py`

---

## 5. Subsystem 4: Multi-Format Exploder

### 5.1 Purpose
From one anchor asset, produce 8 platform-native outputs. Each adaptation is redesigned for that platform's format, audience psychology, and content conventions — not a cross-post.

### 5.2 Outputs per Cycle

| Platform | Output | Format | Primary Goal |
|----------|--------|--------|-------------|
| Blog (anchor) | Full article with AdSense | HTML + Schema | Ad revenue + affiliate + email capture |
| X | Thread (8-12 posts) | Text, each post advancing argument | Traffic → blog |
| LinkedIn | Article + post | Expanded for professionals | Authority + traffic |
| TikTok | Script (30-60s) | Hook → demo → CTA | Brand awareness |
| Instagram | Carousel text | Slide-by-slide narrative | Traffic + email capture |
| Pinterest | Pin descriptions | Short, visual-first | Traffic → blog |
| Medium | Republished article | Adapted for Medium audience | Backlinks + traffic |
| Email | Lead magnet + sequence (5-7 emails) | D1: delivery, D3: value, D7: deep dive, D14: pick+link, D30: check-in | Conversion |

### 5.3 Platform Awareness
Each adaptation queries the brain's platform-specific domain (X/, LinkedIn/, TikTok/, Instagram/) for:
- Platform-specific copywriting principles
- Character/format limits
- Best posting times and frequencies
- What works on that platform for affiliate content

### 5.4 File: `abvorn/exploder/adapters.py`
- `adapt_for_x(anchor) → list[str]` — 8-12 tweet thread
- `adapt_for_linkedin(anchor) → dict` — article + post
- `adapt_for_tiktok(anchor) → dict` — script + caption
- `adapt_for_instagram(anchor) → list[str]` — carousel slides
- `adapt_for_pinterest(anchor) → dict` — pin description
- `adapt_for_medium(anchor) → str` — republished article

### 5.5 File: `abvorn/exploder/email.py`
- `generate_lead_magnet(anchor) → dict` — cheat sheet / checklist / comparison
- `generate_sequence(anchor, persona) → list[EmailStep]` — 5-7 email sequence

### 5.6 File: `abvorn/exploder/__init__.py`

---

## 6. Subsystem 5: Email CRM

### 6.1 Purpose
Capture emails via lead magnets, deliver automated sequences, track engagement, drive conversions. Each persona gets a tailored sequence.

### 6.2 Data Model

```python
Subscriber {
  email, persona_id, niche
  subscribed_at, last_open_at, last_click_at
  sequence_step: int
  total_conversions: int
  total_revenue: float
  status: active | unsubscribed | bounced
}
```

### 6.3 Sequence Template (per persona)
```
Day 1:  Delivery — "Here's your [lead magnet]"
Day 3:  Value — "3 mistakes [persona] makes when buying [product]"
Day 7:  Deep dive — "Why [specific product] solves [specific pain]"
Day 14: Pick + affiliate link — "Still deciding? Here's my pick"
Day 30: Check-in — "How's it going? Also, have you seen [related niche]?"
```

### 6.4 Delivery
For Phase 3, email is **generated and staged for manual sending** via your email provider. Future phase: auto-send via API (Mailgun, SendGrid, etc.)

### 6.5 File: `abvorn/crm/subscriber.py`
- `SubscriberDB` — SQLite-backed subscriber storage

### 6.6 File: `abvorn/crm/__init__.py`

---

## 7. Subsystem 6: Deploy & Analyze

### 7.1 Blog Deployment
- GitHub Pages (existing `GitHubDeployer`) — full HTML with schema, AdSense ad slots, affiliate links, lead magnet CTA
- AdSense integration: auto-ads code in `<head>`, manual ad units at natural break points (pre-content, mid-content, post-content)
- SEO: canonical URLs, meta tags, Open Graph, Twitter Cards, schema.org markup

### 7.2 Social Platform Deployment
- X: API posting (tweet thread via Twitter API)
- LinkedIn: API posting (article via LinkedIn API)
- TikTok/IG/Pinterest: export as formatted drafts (manual publish or future API)
- Medium: API posting via Medium API

### 7.3 Analytics
- GA4 (existing): page views, user engagement, traffic sources
- Affiliate: click tracking, conversion tracking per post/persona
- AdSense: revenue per page, RPM
- Email: open rates, click rates, conversion per sequence step
- All analytics feed back into the Performance Feedback Loop

### 7.4 File: `abvorn/deploy/social.py`
- `post_to_x(content) → dict`
- `post_to_linkedin(content) → dict`
- `export_tiktok(content) → str` — formatted script
- `export_instagram(content) → list[str]` — carousel slides
- `post_to_medium(content) → dict`

---

## 8. Subsystem 7: Self-Driving Orchestrator

### 8.1 Purpose
Run 24/7 with zero human attention. Prioritize work, manage failures, schedule cycles, alert on critical issues.

### 8.2 Cycle
```
1. Check queue for highest-priority opportunity
2. Discover/refresh personas for that niche
3. Select best persona for this cycle
4. Generate anchor content (persuasion pipeline)
5. Explode to all platforms + email sequence
6. Deploy blog + social + stage email
7. Wait for performance data
8. Feed back into brain + personas
9. Repeat
```

### 8.3 Priority Queue
Items scored by: opportunity_score × persona_confidence × time_since_last_post

### 8.4 Failure Recovery
- Transient failures (API timeout): retry with exponential backoff (1s, 2s, 4s, 8s, 16s — max 5)
- Persistent failures (auth expired, API changed): alert via Telegram, skip to next cycle
- Content generation failure (model returns garbage): retry once with stricter prompt, then skip

### 8.5 Health Monitoring
- Heartbeat check every 60 seconds
- Stuck cycle detection (no progress in 30 minutes → alert)
- Cost tracking (daily budget cap → pause if exceeded)
- Success rate tracking per subsystem

### 8.6 File: `abvorn/orchestrator/scheduler.py`
- `Scheduler` — priority queue management, cycle scheduling

### 8.7 File: `abvorn/orchestrator/health.py`
- `HealthMonitor` — heartbeat checks, stuck detection, alerts

---

## 9. Data Model Changes

### 9.1 New Tables in `AbvornState`

```sql
-- Persona registry (extended from Phase 1)
ALTER TABLE persona_registry ADD COLUMN awareness_level TEXT;
ALTER TABLE persona_registry ADD COLUMN lf8_desire TEXT;
ALTER TABLE persona_registry ADD COLUMN cialdini_principles TEXT;
ALTER TABLE persona_registry ADD COLUMN total_revenue REAL DEFAULT 0.0;

-- Subscribers
CREATE TABLE subscribers (
  email TEXT PRIMARY KEY,
  persona_id TEXT,
  niche TEXT,
  subscribed_at TEXT NOT NULL,
  last_open_at TEXT,
  last_click_at TEXT,
  sequence_step INT DEFAULT 0,
  total_conversions INT DEFAULT 0,
  total_revenue REAL DEFAULT 0.0,
  status TEXT DEFAULT 'active'
);

-- Email sequences
CREATE TABLE email_sequences (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  niche TEXT NOT NULL,
  persona_id TEXT,
  day INT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  lead_magnet TEXT,
  sent_count INT DEFAULT 0,
  open_count INT DEFAULT 0,
  click_count INT DEFAULT 0,
  created_at TEXT NOT NULL
);

-- Opportunities
CREATE TABLE opportunities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  niche TEXT NOT NULL,
  score REAL NOT NULL,
  search_volume INT,
  competition REAL,
  commission REAL,
  status TEXT DEFAULT 'pending',
  created_at TEXT NOT NULL,
  last_post_at TEXT
);
```

### 9.2 Migration
Existing `persona_registry` data migrates with default values for new columns.

---

## 10. File Structure (New/Modified)

```
abvorn/
├── discovery/          # NEW — Opportunity discovery
│   ├── __init__.py
│   └── scanner.py
├── persona/            # NEW — Persona engine
│   ├── __init__.py
│   ├── engine.py
│   └── registry.py
├── factory/            # NEW — Content factory (replaces content/)
│   ├── __init__.py
│   ├── pipeline.py     # Full persuasion pipeline
│   └── persuasion.py   # Modular prompt builders per stage
├── content/            # MODIFIED — Repurpose as bridge to factory
│   └── pipeline.py     # Thin wrapper calling factory
├── exploder/           # NEW — Multi-format adaptation
│   ├── __init__.py
│   ├── adapters.py     # Platform adapters
│   └── email.py        # Lead magnet + sequence generation
├── crm/                # NEW — Email CRM
│   ├── __init__.py
│   └── subscriber.py
├── deploy/
│   ├── social.py       # NEW — Social platform posting
│   ├── github.py       # EXISTING — modified for AdSense
│   ├── visual.py       # EXISTING — Open Design bridge
│   └── analytics.py    # EXISTING
├── orchestrator/       # NEW — Self-driving
│   ├── __init__.py
│   ├── scheduler.py
│   └── health.py
├── daemon.py           # MODIFIED — wire new subsystems
├── __main__.py         # MODIFIED — new CLI commands
└── core/
    ├── state.py        # MODIFIED — new tables
    └── bus.py          # EXISTING
```

---

## 11. Implementation Order

### Phase 3a — Foundation (Week 1)
1. Opportunity scanner + scoring
2. Persona engine + registry with lifecycle
3. Data model extensions (new tables, migration)

### Phase 3b — Core Content (Week 2)
4. Content factory with persuasion pipeline
5. Lead magnet + email sequence generation
6. Multi-format adapters (blog → X, LinkedIn, TikTok, IG, Pinterest, Medium)

### Phase 3c — Deploy & Monetize (Week 3)
7. Social platform API posting
8. AdSense integration in blog template
9. Email CRM subscriber database

### Phase 3d — Autonomy (Week 4)
10. Self-driving orchestrator (scheduler + health)
11. Performance feedback loop
12. Full test suite + integration verification

---

## 12. Testing Strategy

### 12.1 Unit Tests
- `tests/test_discovery.py` — opportunity scoring
- `tests/test_persona.py` — persona discovery, lifecycle, retirement
- `tests/test_factory.py` — persuasion pipeline output structure
- `tests/test_exploder.py` — each platform adapter produces correct format
- `tests/test_crm.py` — subscriber management, sequence generation
- `tests/test_orchestrator.py` — priority queue, failure recovery

### 12.2 Integration Tests
- `tests/test_cycle.py` — full cycle: discover → persona → factory → explode → deploy
- `tests/test_feedback.py` — performance data → brain update → next cycle improvement

### 12.3 Target: 25+ tests, all passing