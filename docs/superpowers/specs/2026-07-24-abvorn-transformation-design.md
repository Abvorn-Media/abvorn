# Abvorn v14 — From Simulation to Sovereignty

## The Diagnosis

Abvorn v13 is a **batch script wearing an empire costume**. It runs in a single thread, stores
state in a JSON file vulnerable to corruption, generates content in one-shot LLM calls, and
labels ChromaDB collections as "Generals." Its GA4 feedback loop is dead code. Its "self-evolution"
moves markdown files between folders. Its content quality is self-rated by the same model that
wrote it. It has no persistence, no concurrency, and no genuine autonomous behavior.

## The Vision

What if Abvorn actually **was** the thing it claims to be?

A persistent, living system where:

- **Real agents** with tools, memory, and decision rights operate around the clock
- **Content** is researched, drafted, fact-checked, revised, and quality-scored by specialized agents working in a pipeline, not a single AI call
- **Distribution** is automatic — email, social, RSS, cross-linking — all driven by real performance data
- **Evolution** means the system rewrites its own prompts, adds new agents, and reconfigures its pipeline based on measured outcomes
- **The feedback loop** is real: GA4 data → persona performance → content strategy → content generation → GA4 data

---

## Phase 1 — The Foundation (Ship This Week)

### 1. Kill the Colab Dependence

**Problem:** `drive.mount('/content/drive')` crashes the entire system if Drive isn't
mounted. Secrets, state, skills — everything lives on Drive. No local fallback.

**Solution:** Split into two paths:

```
local/              # Runs anywhere (your machine, VPS, GHA)
  secrets.json      # Local copy, no Drive mount needed
  state/            # SQLite-backed state (not JSON files)
  output/           # Staging area before deploy
colab/              # Backward-compat for Colab users
  cell1.py, cell2.py, cell3.py  # Thin wrappers that call local/ logic
```

**Key change:** The core engine becomes Python package `abvorn/` with proper
modules, not Colab cells. The Colab cells become import + orchestration only.

**Files to create:**
```
abvorn/
  __init__.py
  core/
    secrets.py       # Secret loading with Drive + env + local fallback
    state.py         # SQLite-backed state with proper locking
    models.py        # AI client pool (not a single ask_ai function)
  agents/
    base.py          # Base agent class with tools, memory, lifecycle
    researcher.py    # Web research agent (uses Agent Reach)
    writer.py        # Content generation agent (uses multi-step pipeline)
    editor.py        # Quality & fact-check agent
    strategist.py    # Content strategy from GA4 data
  content/
    pipeline.py      # Multi-step content pipeline
    templates.py     # HTML/CSS templates
    seo.py           # SEO validation, schema generation
  deploy/
    github.py        # GitHub Pages deployment
    social.py        # Social media posting (Composio)
    email.py         # Email sending pipeline
```

### 2. SQLite State (Kill the JSON File)

**Problem:** `empire_state.json` is read/written by overlapping GHA runs. No locking.
Corruption = complete reset. ChromaDB is not multi-process safe.

**Solution:** One SQLite database with WAL mode for concurrency:

```sql
-- Single database, properly locked, atomic transactions
CREATE TABLE state (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE niches (
  slug TEXT PRIMARY KEY, name TEXT, category TEXT,
  maturity TEXT, total_posts INT, avg_quality REAL,
  ga4_views INT, ga4_users INT, ga4_score REAL,
  created_at TEXT, last_post_at TEXT
);
CREATE TABLE posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  niche_slug TEXT REFERENCES niches(slug),
  title TEXT, filename TEXT, product_name TEXT,
  angle TEXT, quality_score REAL, persona_id TEXT,
  deployment_status TEXT, created_at TEXT
);
CREATE TABLE queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  niche_slug TEXT, stage TEXT, priority INT,
  created_at TEXT, locked_until TEXT
);
```

**Benefits:**
- WAL mode allows concurrent readers/writers
- Atomic transactions prevent partial writes
- No silent corruption = blank state
- Easy to query: "show me niches with ga4_views > 100 and avg_quality < 7"
- ChromaDB becomes optional — store embeddings in SQLite too

### 3. Multi-Step Content Pipeline (Kill the One-Shot Generate)

**Problem:** A single `ask_ai()` call generates an entire 2000-word article with product
comparisons, FAQ, schema, and social posts. No iteration. No fact-checking. The AI
hallucinates products. Quality is self-rated.

**Solution:** A 5-stage pipeline with specialized agents:

```
RESEARCH → OUTLINE → DRAFT → FACT-CHECK → POLISH
```

**Stage 1 — RESEARCH agent:**
- Searches web for real products in this niche (Agent Reach + DuckDuckGo)
- Extracts real prices, real features, real pros/cons from search snippets
- Returns structured data: `[{name, price, rating, features, pros, cons, source_url}]`
- **No more hallucinated products**

**Stage 2 — OUTLINE agent:**
- Persona + research data + niche maturity → content angle selection
- Produces a structured outline with H2 headings and key points per section
- Human-reviewable before committing to full generation

**Stage 3 — DRAFT agent:**
- Outline + research + persona + persuasion knowledge → first draft
- Writes section by section, not one-shot. Each section has a clear purpose.
- Produces SEO metadata, social posts, lead magnet

**Stage 4 — FACT-CHECK agent:**
- Verifies every factual claim against research data
- Flags claims that aren't supported by the research
- If confidence < threshold, sends back to RESEARCH for more data
- Returns: `{passed: bool, issues: [{claim, evidence, severity}], revised_draft: str}`

**Stage 5 — POLISH agent:**
- Refines tone, readability, conversion architecture
- Generates final schema markup
- Produces quality score (based on measurable criteria, not self-rating)

### 4. Real GA4 Feedback Loop (Fix the Dead Code)

**Problem:** `GA4_PROPERTY_ID` is missing from GHA secrets. Even if it were present,
the data is collected but never used to change content decisions.

**Solution:**
- Add `GA4_PROPERTY_ID` and `GA4_CREDENTIALS_JSON` to GHA secrets
- After each deploy cycle, pull last-28-days analytics
- Feed GA4 data into the strategist agent:

```python
def strategist_feedback_loop():
    analytics = pull_ga4_analytics()  # real GA4 data now
    for slug, data in analytics.items():
        niche = get_niche(slug)
        niche.ga4_views = data['views']
        niche.ga4_users = data['users']
        niche.ga4_score = (data['views'] + data['users'] * 2 + data['avg_duration'] / 10)
        # Auto-decide: double down or pivot
        if niche.ga4_score > 100 and niche.quality_score > 7:
            niche.priority = 'high'  # produce more content for this niche
        elif niche.ga4_score < 10 and niche.total_posts > 3:
            niche.priority = 'low'   # stop investing
            # Or try a different content angle / persona
```

---

## Phase 2 — True Agents (Ship This Month)

### 5. Replace Fake Generals With Real Agents

**Problem:** Generals are ChromaDB collections + markdown files. They don't DO anything.
No autonomous behavior. No tools. No message passing.

**Solution:** Each General is a proper agent with:

```
General of Research:
  - Tools: web_search, fetch_url, extract_prices, Agent Reach
  - Memory: previous research findings, niche knowledge graph
  - Schedule: runs continuously, not just during batch cycles
  - Output: structured research reports consumable by other agents

General of Persuasion:
  - Tools: read_ceo_library, analyze_content, query_persona
  - Memory: what conversion patterns work (measured, not guessed)
  - Output: persuasion frameworks for each niche/persona

General of Distribution:
  - Tools: post_to_x, post_to_instagram, send_email, update_rss
  - Memory: what posting times/formats drive engagement
  - Output: multi-platform distribution plan per content piece

General of Strategy:
  - Tools: read_analytics, query_niche_db, analyze_market
  - Memory: market trends, competitor moves, seasonal patterns
  - Output: which niches to pursue, what angles to try

General of Evolution:
  - Tools: read_code, write_code, run_tests, deploy_change
  - Memory: what changes improved outcomes, what broke things
  - Output: actual code changes (not proposals)
```

**The agent lifecycle:**
```
Idle → Perceives (reads state, analytics, market) → 
Decides (what to do) → Acts (uses tools) → 
Reflects (did it work?) → Learns (updates memory) → Idle
```

Each agent runs in its own `asyncio` task (or `thread`), with message passing
through a shared queue/event bus. No more sequential batch processing.

### 6. Agent Communication Bus

**Problem:** Currently, all "communication" is through shared JSON files and ChromaDB.
There's no event-driven coordination.

**Solution:** A lightweight message bus (in-process, SQLite-backed):

```python
class AgentBus:
    def publish(self, topic: str, message: dict):
        # Store in SQLite, notify subscribers
        pass
    
    def subscribe(self, topic: str, callback):
        # Register interest in topics
        pass
```

Topics:
- `content.researched` — RESEARCH agent finished → DRAFT agent picks up
- `content.drafted` — DRAFT agent finished → EDITOR agent picks up  
- `content.published` — Deploy complete → DISTRIBUTION agent picks up
- `analytics.updated` — GA4 data refreshed → STRATEGY agent re-evaluates
- `system.error` — Any agent failure → EVOLUTION agent diagnoses
- `evolution.patch` — EVOLUTION agent has a change → system hot-reloads

### 7. Continuous Operation (Not Cron)

**Problem:** GHA runs twice daily. 45-minute timeout. Content generation can take
10-20 minutes per niche. The system only exists when a runner spins up.

**Solution:** Run on your own infrastructure (or a cheap VPS):

```bash
# abvorn daemon — runs 24/7
$ python -m abvorn daemon
# or Docker
$ docker run -d --name abvorn \
    -v /path/to/data:/data \
    -e OPENAI_KEY=... \
    abvorn/daemon:latest
```

The daemon:
- Runs all agents as async tasks
- Processes queue continuously (not in batches)
- Responds to Telegram commands in real-time (not polled every 5 seconds)
- Deploys to GitHub Pages on each content completion (not batched)
- Sends email immediately when someone subscribes (not next cycle)
- Self-heals: if an agent crashes, restarts it

---

## Phase 3 — Evolution & Scale (Next 30 Days)

### 8. Real Self-Modification

**Problem:** Self-evolution is moving `.md` files and writing proposals to GitHub.
Nothing actually changes how the system behaves.

**Solution:** The Evolution agent can:
- Read its own prompt files and agent configurations
- A/B test prompt variants (run two versions, measure which produces better content)
- Generate improved prompts based on measured outcomes
- Hot-reload prompts without restarting (file watcher)
- Generate entirely new agent types when capability gaps are detected

**Example:**
```
Evolution agent notices: "Niche 'wireless_headphones' has high ga4_views (500) 
but low conversion. Current prompt doesn't emphasize comparison tables for 
tech-savvy personas. Testing prompt variant B with stronger comparison framing."

→ Runs prompt B for next 3 posts in this niche
→ Measures conversion difference (via affiliate click tracking)
→ If B > A by 15%+, updates the prompt permanently for tech-savvy personas
```

### 9. Distribution Layer (Stop Leaking Value)

**Problem:** Content goes to GitHub Pages. Social media tries Composio (likely fails).
Email never actually sends. No content repurposing.

**Solution:**

```
Content created → 
  1. HTML post to GitHub Pages (works today)
  2. Auto-generated social posts (X, LinkedIn, Pinterest) via Composio
     with proper fallback if Composio is down
  3. Email blast to subscribers in that niche (template + send)
  4. Auto-generated TikTok script (15-30 sec) + Pinterest pin
  5. Cross-links to related niches (works today, but needs improvement)
  6. RSS feed update (works today)
  → Each distribution channel reports back: clicks, views, conversions
  → Distribution agent learns which channels perform for which niches
```

### 10. Real Product Data

**Problem:** Products are hallucinated by AI. Affiliate links go to Amazon search
URLs (not product pages). No real pricing.

**Solution:** Use Agent Reach + web search to find real products:

```python
def research_product(niche):
    # Agent Reach: search web for "best {niche} 2025"
    # Extract: product name, price, rating, affiliate link
    # Cross-reference 3+ sources before accepting
    # Store in product database (not regenerated each time)
    
    products = agent_reach.research(f"best {niche} 2025")
    for p in products:
        p.deep_link = find_amazon_deep_link(p.name)  # real ASIN link
        p.price_history = track_price(p.name)         # price over time
        p.verified_reviews = extract_reviews(p.name)  # real review snippets
    return products
```

---

## Migration Path

### Week 1: Foundation
1. Create `abvorn/` package with modular structure
2. Replace `empire_state.json` with SQLite
3. Fix GA4 feedback loop (add missing secrets)
4. Keep Colab cells as thin wrappers for backward compat
5. Deploy as-is to verify nothing breaks

### Week 2: Multi-Step Pipeline
1. Build RESEARCH agent (web search for real products)
2. Build OUTLINE → DRAFT → FACT-CHECK → POLISH pipeline
3. Remove one-shot content generation
4. Verify content quality improvement with real GA4 data

### Week 3: True Agents
1. Build AgentBus (message passing)
2. Convert General of Research to real agent
3. Convert General of Persuasion to real agent
4. Convert General of Distribution to real agent
5. Run all three as async tasks, observe coordination

### Week 4: Evolution & Scale
1. Build daemon mode (continuous operation)
2. Build Evolution agent (prompt A/B testing)
3. Build email distribution pipeline
4. Fix social media posting
5. Product database with real pricing

---

## What Stays

Not everything is broken. Keep:

- **The SOUL / Mission / Values** — the strategic north star is excellent
- **The SOUL prompt itself** — best version of "who we are" for the AI
- **The design system** — CSS, templates, product cards are genuinely good
- **The persona system** — concept is sound, just needs real data driving it
- **The content angle system** — good framework, needs actual enforcement
- **The niche maturity model** — excellent for prioritizing where to invest
- **The deploy pipeline** — GitHub Pages deploys work (when they run to completion)
- **The SEO audit** — good checks, just needs to run before deploy (it does already)
- **The Telegram command interface** — useful for remote control

## What Gets Replaced

- Colab cells → proper Python package
- empire_state.json → SQLite
- One-shot content → multi-step pipeline
- Fake Generals → real agents
- Hallucinated products → researched products
- Dead GA4 loop → active feedback
- Cron schedule → continuous daemon
- Markdown proposals → hot-reloaded code changes
- Batch deploy → continuous deploy
- Social media "try and fail" → reliable multi-platform posting
- No email pipeline → automated email sequences

---

## The Core Principle

**Stop simulating agency. Build actual agency.**

Every "General" should be a process that:
1. Runs continuously (not when called)
2. Has real tools (not prompt text)
3. Makes decisions (not just fills templates)
4. Learns from outcomes (not self-evaluation)
5. Communicates with other agents (not shared JSON files)
6. Can be measured by its actual impact on the mission

When a General can look at GA4 data, decide "niche X needs a different angle,"
draft a new content strategy, task the Content Captain with executing it, and
then measure whether it worked — *that's* when Abvorn becomes what it claims to be.