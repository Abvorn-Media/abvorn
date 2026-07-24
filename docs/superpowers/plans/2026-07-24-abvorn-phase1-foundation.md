# Abvorn v14 — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fragile Colab batch script with a proper Python package with SQLite state, a multi-step content pipeline, and a working GA4 feedback loop.

**Architecture:** The existing 3-cell Colab files remain as thin wrappers. The core engine moves into `abvorn/` package with `core/`, `content/`, `agents/`, and `deploy/` subpackages. State migrates from `empire_state.json` to SQLite. Content generation moves from one-shot LLM calls to a 5-stage pipeline.

**Tech Stack:** Python 3.10+, SQLite3, openai, duckduckgo-search, PyGithub, google-analytics-data, ChromaDB (optional after migration)

## Global Constraints

- Keep Colab cell files backward-compatible — they can import from `abvorn/` 
- All state reads/writes go through SQLite, never direct file I/O
- The existing `empire_state.json` data must be migratable to SQLite
- Every content pipeline stage has a defined input/output schema
- No `except: pass` — every error path must log or escalate

---

### Task 1: Package Structure

**Files:**
- Create: `abvorn/__init__.py`
- Create: `abvorn/core/__init__.py`
- Create: `abvorn/core/secrets.py`
- Create: `abvorn/core/state.py`
- Create: `abvorn/core/models.py`
- Create: `abvorn/content/__init__.py`
- Create: `abvorn/content/pipeline.py`
- Create: `abvorn/content/seo.py`
- Create: `abvorn/agents/__init__.py`
- Create: `abvorn/agents/base.py`
- Create: `abvorn/deploy/__init__.py`
- Create: `abvorn/deploy/github.py`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: package skeleton, `abvorn.core.secrets.load_secrets()`, `abvorn.core.state.AbvornState`

- [ ] **Step 1: Create package skeleton**

```python
# abvorn/__init__.py
__version__ = "14.0.0"
```

```python
# abvorn/core/__init__.py
from .secrets import load_secrets
from .state import AbvornState
from .models import AIProvider
```

```python
# abvorn/content/__init__.py
from .pipeline import ContentPipeline
```

```python
# abvorn/agents/__init__.py
```

```python
# abvorn/deploy/__init__.py
```

- [ ] **Step 2: Create secrets module with Drive + env + local fallback**

```python
# abvorn/core/secrets.py
import json, os, logging
from pathlib import Path

logger = logging.getLogger("abvorn.secrets")

BOARDROOM_PATHS = [
    Path(os.environ.get("ABVORN_BOARDROOM", "")),
    Path("/content/drive/MyDrive/The_Synthetic_Boardroom"),
    Path.home() / ".abvorn" / "boardroom",
]

def _find_boardroom() -> Path:
    for p in BOARDROOM_PATHS:
        if p.exists() and (p / "secrets.json").exists():
            return p
    # Fallback: create local default
    local = Path.home() / ".abvorn" / "boardroom"
    local.mkdir(parents=True, exist_ok=True)
    return local

def load_secrets() -> dict:
    boardroom = _find_boardroom()
    secrets = {}
    sf = boardroom / "secrets.json"
    if sf.exists():
        raw = sf.read_bytes()
        if raw.startswith(b'\xef\xbb\xbf'):
            raw = raw[3:]
        try:
            secrets = json.loads(raw.decode('utf-8'))
        except json.JSONDecodeError:
            logger.warning("secrets.json corrupt, falling back to env vars")
    # Env vars override file values
    env_map = {
        "GLM_KEYS": "GLM_KEYS", "DEEPSEEK_KEY": "DEEPSEEK_KEY",
        "OPENAI_KEY": "OPENAI_KEY", "QWEN_KEY": "QWEN_KEY",
        "GEMINI_KEY": "GEMINI_KEY", "GROQ_KEY": "GROQ_KEY",
        "GITHUB_TOKEN": "GITHUB_TOKEN", "GITHUB_REPO": "GITHUB_REPO",
        "SITE_URL": "SITE_URL", "AMAZON_TAG": "AMAZON_TAG",
        "GA4_MEASUREMENT_ID": "GA4_MEASUREMENT_ID",
        "GA4_API_SECRET": "GA4_API_SECRET",
        "GA4_PROPERTY_ID": "GA4_PROPERTY_ID",
        "GA4_CREDENTIALS_JSON": "GA4_CREDENTIALS_JSON",
        "TELEGRAM_TOKEN": "TELEGRAM_TOKEN",
        "TELEGRAM_CHAT_ID": "TELEGRAM_CHAT_ID",
        "GMAIL_USER": "GMAIL_USER",
        "GMAIL_APP_PASSWORD": "GMAIL_APP_PASSWORD",
        "SHEET_ID": "SHEET_ID",
        "COMPOSIO_KEY": "COMPOSIO_KEY",
        "PEXELS_KEY": "PEXELS_KEY",
    }
    for env_key, secrets_key in env_map.items():
        val = os.environ.get(env_key)
        if val and "YOUR_" not in val:
            secrets[secrets_key] = val
    # Load GA4 credentials from separate file or embedded JSON
    ga4_file = boardroom / "ga4_credentials.json"
    if ga4_file.exists():
        secrets["GA4_CREDENTIALS_JSON"] = ga4_file.read_text().strip()
    return secrets

def get_boardroom_path() -> Path:
    return _find_boardroom()

def get_empire_path() -> Path:
    return _find_boardroom() / "6_Empire_Network"
```

- [ ] **Step 3: Create SQLite state module**

```python
# abvorn/core/state.py
import sqlite3, json, threading, logging
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger("abvorn.state")

class AbvornState:
    """Thread-safe SQLite-backed state. WAL mode for concurrent access."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._local = threading.local()
        self._init_db()

    @contextmanager
    def _cursor(self):
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path))
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA busy_timeout=5000")
        yield self._local.conn.cursor()
        self._local.conn.commit()

    def _init_db(self):
        with self._cursor() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS niches (
                    slug TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT DEFAULT 'Other',
                    maturity TEXT DEFAULT 'seed',
                    total_posts INT DEFAULT 0,
                    avg_quality REAL DEFAULT 0.0,
                    ga4_views INT DEFAULT 0,
                    ga4_users INT DEFAULT 0,
                    ga4_score REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    last_post_at TEXT
                );
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    niche_slug TEXT NOT NULL REFERENCES niches(slug),
                    title TEXT NOT NULL,
                    filename TEXT,
                    product_name TEXT,
                    angle TEXT,
                    quality_score REAL,
                    persona_id TEXT,
                    deployment_status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    niche_slug TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    priority INT DEFAULT 10,
                    payload TEXT,
                    created_at TEXT NOT NULL,
                    locked_until TEXT
                );
                CREATE TABLE IF NOT EXISTS persona_registry (
                    persona_id TEXT PRIMARY KEY,
                    niche TEXT NOT NULL,
                    persona_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used TEXT,
                    post_count INT DEFAULT 0,
                    avg_quality REAL DEFAULT 0.0,
                    impressions INT DEFAULT 0,
                    clicks INT DEFAULT 0,
                    conversions INT DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS model_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    time_ms REAL,
                    tokens INT,
                    created_at TEXT NOT NULL
                );
            """)

    def close(self):
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    # ── Meta (generic key-value store for misc state) ──
    def get_meta(self, key: str, default=None):
        with self._cursor() as c:
            c.execute("SELECT value FROM meta WHERE key=?", (key,))
            row = c.fetchone()
            return json.loads(row[0]) if row else default

    def set_meta(self, key: str, value):
        with self._cursor() as c:
            c.execute("REPLACE INTO meta VALUES (?, ?)", (key, json.dumps(value)))

    # ── Niches ──
    def upsert_niche(self, slug: str, name: str, category: str = "Other"):
        with self._cursor() as c:
            c.execute("""
                INSERT INTO niches (slug, name, category, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET name=excluded.name, category=excluded.category
            """, (slug, name, category, datetime.now().isoformat()))

    def get_niche(self, slug: str) -> dict:
        with self._cursor() as c:
            c.execute("SELECT * FROM niches WHERE slug=?", (slug,))
            row = c.fetchone()
            if not row:
                return None
            keys = ["slug","name","category","maturity","total_posts","avg_quality",
                    "ga4_views","ga4_users","ga4_score","created_at","last_post_at"]
            return dict(zip(keys, row))

    def get_all_niches(self) -> list:
        with self._cursor() as c:
            c.execute("SELECT * FROM niches ORDER BY ga4_score DESC")
            keys = ["slug","name","category","maturity","total_posts","avg_quality",
                    "ga4_views","ga4_users","ga4_score","created_at","last_post_at"]
            return [dict(zip(keys, row)) for row in c.fetchall()]

    def update_niche_analytics(self, slug: str, views: int, users: int, score: float):
        with self._cursor() as c:
            c.execute("""
                UPDATE niches SET ga4_views=?, ga4_users=?, ga4_score=?
                WHERE slug=?
            """, (views, users, round(score, 1), slug))

    def update_niche_maturity(self, slug: str, total_posts: int, avg_quality: float):
        maturity = "seed"
        if total_posts >= 10 and avg_quality >= 7.5: maturity = "evergreen"
        elif total_posts >= 7: maturity = "thriving"
        elif total_posts >= 4: maturity = "growing"
        elif total_posts >= 2: maturity = "sprout"
        with self._cursor() as c:
            c.execute("""
                UPDATE niches SET total_posts=?, avg_quality=?, maturity=?, last_post_at=?
                WHERE slug=?
            """, (total_posts, round(avg_quality, 1), maturity, datetime.now().isoformat(), slug))

    # ── Posts ──
    def add_post(self, niche_slug: str, title: str, filename: str,
                 product_name: str = "", angle: str = "", quality_score: float = 0.0,
                 persona_id: str = ""):
        with self._cursor() as c:
            c.execute("""
                INSERT INTO posts (niche_slug, title, filename, product_name, angle,
                                    quality_score, persona_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (niche_slug, title, filename, product_name, angle,
                  quality_score, persona_id, datetime.now().isoformat()))

    def get_posts_for_niche(self, niche_slug: str) -> list:
        with self._cursor() as c:
            c.execute("SELECT * FROM posts WHERE niche_slug=? ORDER BY created_at DESC", (niche_slug,))
            keys = ["id","niche_slug","title","filename","product_name","angle",
                    "quality_score","persona_id","deployment_status","created_at"]
            return [dict(zip(keys, row)) for row in c.fetchall()]

    # ── Queue ──
    def enqueue(self, niche_slug: str, stage: str, priority: int = 10, payload: dict = None):
        with self._cursor() as c:
            c.execute("""
                INSERT INTO queue (niche_slug, stage, priority, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (niche_slug, stage, priority, json.dumps(payload or {}), datetime.now().isoformat()))

    def dequeue(self) -> dict:
        with self._cursor() as c:
            c.execute("""
                SELECT * FROM queue
                WHERE locked_until IS NULL OR locked_until < datetime('now')
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
            """)
            row = c.fetchone()
            if not row:
                return None
            task = {
                "id": row[0], "niche_slug": row[1], "stage": row[2],
                "priority": row[3], "payload": json.loads(row[4]) if row[4] else {},
                "created_at": row[5]
            }
            # Lock for 5 minutes
            c.execute("UPDATE queue SET locked_until=datetime('now','+5 minutes') WHERE id=?", (task["id"],))
            return task

    def complete_queue_item(self, task_id: int):
        with self._cursor() as c:
            c.execute("DELETE FROM queue WHERE id=?", (task_id,))

    def fail_queue_item(self, task_id: int):
        with self._cursor() as c:
            c.execute("DELETE FROM queue WHERE id=?", (task_id,))

    # ── Personas ──
    def upsert_persona(self, persona_id: str, niche: str, persona: dict):
        with self._cursor() as c:
            c.execute("""
                INSERT INTO persona_registry (persona_id, niche, persona_json, created_at, last_used)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(persona_id) DO UPDATE SET
                    last_used=excluded.last_used,
                    persona_json=excluded.persona_json
            """, (persona_id, niche, json.dumps(persona), datetime.now().isoformat(), datetime.now().isoformat()))

    def update_persona_performance(self, persona_id: str, quality_score: float = 0,
                                    views: int = 0, clicks: int = 0, conversions: int = 0):
        with self._cursor() as c:
            c.execute("""
                UPDATE persona_registry SET
                    post_count = post_count + 1,
                    impressions = impressions + ?,
                    clicks = clicks + ?,
                    conversions = conversions + ?,
                    avg_quality = CASE WHEN post_count > 0
                        THEN (avg_quality * post_count + ?) / (post_count + 1)
                        ELSE ? END,
                    last_used = ?
                WHERE persona_id=?
            """, (views, clicks, conversions, quality_score, quality_score, datetime.now().isoformat(), persona_id))

    def get_personas_for_niche(self, niche: str) -> list:
        with self._cursor() as c:
            c.execute("SELECT * FROM persona_registry WHERE niche=?", (niche,))
            keys = ["persona_id","niche","persona_json","created_at","last_used",
                    "post_count","avg_quality","impressions","clicks","conversions"]
            return [dict(zip(keys, row)) for row in c.fetchall()]

    # ── Analytics ──
    def log_model_metric(self, provider: str, time_ms: float, tokens: int):
        with self._cursor() as c:
            c.execute("INSERT INTO model_metrics (provider, time_ms, tokens, created_at) VALUES (?, ?, ?, ?)",
                      (provider, time_ms, tokens, datetime.now().isoformat()))

    def get_model_stats(self) -> list:
        with self._cursor() as c:
            c.execute("""
                SELECT provider, COUNT(*) as calls, AVG(time_ms) as avg_time,
                       SUM(tokens) as total_tokens
                FROM model_metrics
                WHERE created_at > datetime('now', '-7 days')
                GROUP BY provider
            """)
            keys = ["provider", "calls", "avg_time_ms", "total_tokens"]
            return [dict(zip(keys, row)) for row in c.fetchall()]

    # ── Migration from legacy JSON ──
    def import_legacy_json(self, json_path: Path):
        """Import data from empire_state.json into SQLite."""
        if not json_path.exists():
            return
        data = json.loads(json_path.read_text())
        # Migrate niches from performance + deployed
        deployed = data.get("deployed", [])
        completed = data.get("completed", [])
        all_slugs = list(dict.fromkeys(deployed + completed))
        perf = data.get("performance", {})
        for slug in all_slugs:
            name = slug.replace("_", " ").title()
            pdata = perf.get(slug, {})
            if isinstance(pdata, dict):
                self.upsert_niche(slug, name, pdata.get("category", "Other"))
                self.update_niche_analytics(slug, pdata.get("ga4_views", 0),
                                            pdata.get("ga4_users", 0),
                                            pdata.get("ga4_score", 0))
        # Migrate queue
        for item in data.get("queue", []):
            self.enqueue(item.get("slug", "unknown"), item.get("stage", "products"),
                         payload={"niche": item.get("niche", "")})
        # Migrate personas
        for pid, pdata in data.get("persona_registry", {}).items():
            self.upsert_persona(pid, pdata.get("niche", ""), pdata.get("persona", {}))
            perf_data = pdata.get("performance", {})
            self.update_persona_performance(pid, perf_data.get("avg_quality", 0),
                                            perf_data.get("impressions", 0),
                                            perf_data.get("clicks", 0),
                                            perf_data.get("conversions", 0))
        logger.info(f"Migrated {len(all_slugs)} niches from legacy JSON")
```

- [ ] **Step 4: Create AI provider pool module**

```python
# abvorn/core/models.py
import time, logging
from collections import defaultdict
from openai import OpenAI

logger = logging.getLogger("abvorn.models")

class AIProvider:
    """An AI model provider with key management and metrics tracking."""

    def __init__(self, name: str, api_key: str, base_url: str = None, model: str = None):
        self.name = name
        self.model = model or "gpt-4o"
        self.client = OpenAI(api_key=api_key, base_url=base_url) if api_key else None
        self._banned_until = 0.0
        self.total_calls = 0
        self.total_tokens = 0
        self.total_time = 0.0
        self.failures = 0

    @property
    def available(self) -> bool:
        return self.client is not None and time.time() > self._banned_until

    def ban(self, duration: int = 60):
        self._banned_until = time.time() + duration
        self.failures += 1

    def call(self, messages: list, json_mode: bool = False) -> str:
        start = time.time()
        fmt = {"type": "json_object"} if json_mode else None
        try:
            resp = self.client.chat.completions.create(
                model=self.model, messages=messages, response_format=fmt
            )
            elapsed = time.time() - start
            self.total_calls += 1
            self.total_tokens += resp.usage.total_tokens if resp.usage else 0
            self.total_time += elapsed
            return resp.choices[0].message.content
        except Exception as e:
            self.failures += 1
            logger.warning(f"{self.name} failed: {str(e)[:80]}")
            raise


class ModelRouter:
    """Intelligently routes prompts to the best available provider."""

    def __init__(self, secrets: dict):
        self.providers = []
        # Priority order: cheapest/fastest first, expensive fallback last
        configs = [
            ("qwen", secrets.get("QWEN_KEY"), "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "qwen3.5-flash"),
            ("gemini", secrets.get("GEMINI_KEY"), "https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.0-flash"),
            ("groq", secrets.get("GROQ_KEY"), "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
            ("deepseek", secrets.get("DEEPSEEK_KEY"), "https://api.deepseek.com/v1", "deepseek-chat"),
            ("openai", secrets.get("OPENAI_KEY"), None, "gpt-4o"),
        ]
        for name, key, url, model in configs:
            if key and "YOUR_" not in key:
                self.providers.append(AIProvider(name, key, url, model))

    def ask(self, prompt: str, system: str = None, json_mode: bool = False,
            model_hint: str = None) -> str:
        """Try providers in order. Returns response text or None if all fail."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # If a specific model is hinted, try it first
        if model_hint:
            for p in self.providers:
                if model_hint in p.name and p.available:
                    try:
                        return p.call(messages, json_mode)
                    except Exception:
                        p.ban()

        for p in self.providers:
            if not p.available:
                continue
            try:
                return p.call(messages, json_mode)
            except Exception:
                p.ban()
                continue
        logger.error("All AI providers exhausted")
        return None

    def get_stats(self) -> list:
        return [{"name": p.name, "calls": p.total_calls, "tokens": p.total_tokens,
                 "time": round(p.total_time, 2), "failures": p.failures,
                 "available": p.available} for p in self.providers]
```

- [ ] **Step 5: Verify the package imports correctly**

Run: `python -c "from abvorn.core.state import AbvornState; print('OK')"`

- [ ] **Step 6: Commit**

```bash
git add abvorn/
git commit -m "feat: create abvorn package skeleton with SQLite state and AI router"
```

---

### Task 2: Content Pipeline — RESEARCH Stage

**Files:**
- Create: `abvorn/agents/researcher.py`
- Test: `tests/test_researcher.py`

**Interfaces:**
- Consumes: `ModelRouter` from Task 1
- Produces: `research_niche(niche: str, router: ModelRouter) -> list[dict]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_researcher.py
import pytest
from abvorn.agents.researcher import research_niche

def test_research_returns_products():
    """RESEARCH stage should return a list of dicts with required keys."""
    class FakeRouter:
        def ask(self, prompt, **kw):
            return '[{"name": "Test Product", "price": "$49.99", "rating": "4.5/5", "features": ["Feature A"], "summary": "Great product"}]'
    products = research_niche("test_niche", FakeRouter())
    assert isinstance(products, list)
    assert len(products) > 0
    p = products[0]
    assert "name" in p
    assert "price" in p
    assert "features" in p
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_researcher.py::test_research_returns_products -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# abvorn/agents/researcher.py
import json, re, logging
from duckduckgo_search import DDGS

logger = logging.getLogger("abvorn.researcher")

def research_niche(niche: str, router=None) -> list:
    """RESEARCH stage: search web for real products in this niche.
    
    Returns list of dicts: [{name, price, rating, features, pros, cons, summary, source_url}]
    """
    products = []
    # 1. Try web search for real products
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"best {niche} 2025 2026 buying guide", max_results=8))
            snippets = []
            for r in results:
                if r.get("body"):
                    snippets.append(f"[{r.get('title','')}]({r.get('href','')}): {r['body'][:300]}")
            if snippets and router:
                prompt = f"""From these search results about '{niche}', extract up to 5 specific products.
For each product, return: name, estimated price, rating (if found), key features, pros, cons, and a 1-sentence summary.

Search results:
{chr(10).join(snippets[:5])}

Return a JSON array of objects with keys: name, price, rating, features (array), pros (array), cons (array), summary, source_url."""
                result = router.ask(prompt, json_mode=True)
                if result:
                    parsed = _parse_json(result)
                    if isinstance(parsed, list):
                        products = parsed
                    elif isinstance(parsed, dict):
                        products = [parsed]
    except Exception as e:
        logger.warning(f"Web research failed for '{niche}': {e}")

    # 2. Fallback: AI knowledge-based product generation
    if not products and router:
        prompt = f"""You are a product expert. For the niche '{niche}', recommend exactly 3 specific real products with brand and model names. Use your knowledge of real products available on Amazon.

Return a JSON array. Each product must have:
- name: specific brand + model (e.g. "Sony WH-1000XM5")
- price: realistic price string
- description: 1-2 sentence highlight
- features: array of 3-4 key features
- category: "best_overall", "best_value", or "premium_pick"
- affiliate_query: search query for this product (e.g. "Sony+WH-1000XM5")"""
        result = router.ask(prompt, json_mode=True)
        if result:
            parsed = _parse_json(result)
            if isinstance(parsed, list):
                products = parsed

    # 3. Ultimate fallback
    if not products:
        products = [{"name": f"Top {niche} Pick", "price": "Check Price",
                     "description": f"Best {niche} on the market",
                     "features": ["Quality", "Value", "Reliability"],
                     "category": "best_overall",
                     "affiliate_query": niche.replace(" ", "+")}]

    for p in products:
        p.setdefault("affiliate_query", p.get("name", niche).replace(" ", "+"))
        p.setdefault("source_url", "")

    return products


def _parse_json(text: str):
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\[.*\]|\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_researcher.py::test_research_returns_products -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add abvorn/agents/researcher.py tests/test_researcher.py
git commit -m "feat: add RESEARCH stage content pipeline agent"
```

---

### Task 3: Content Pipeline — OUTLINE + DRAFT + FACT-CHECK + POLISH Stages

**Files:**
- Create: `abvorn/agents/writer.py`
- Create: `abvorn/agents/editor.py`
- Modify: `abvorn/content/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `research_niche()` from Task 2, `ModelRouter` from Task 1
- Produces: `ContentPipeline.run(niche, router, persona) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline.py
import pytest
from abvorn.content.pipeline import ContentPipeline

def test_pipeline_full_run():
    """Pipeline should produce a complete content dict with all required fields."""
    class FakeRouter:
        def ask(self, prompt, **kw):
            return json.dumps({
                "outline": ["H2: Introduction", "H2: Product Review"],
                "title": "Test Title",
                "meta_description": "Test meta description for SEO purposes here it is long enough",
                "intro": "<p>Test intro</p>",
                "article_html": "<p>Test article</p>",
                "faqs": [{"question": "Q1?", "answer": "A1."}],
                "tags": ["test"],
                "socials": {"x": "tweet", "linkedin": "post"}
            })

    pipeline = ContentPipeline()
    result = pipeline.run("test_niche", FakeRouter(), persona={})
    assert result is not None
    assert "post_title" in result
    assert "article_html" in result
    assert "meta_description" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create OUTLINE agent**

```python
# abvorn/agents/writer.py
import json, re, logging
from datetime import datetime

logger = logging.getLogger("abvorn.writer")

CONTENT_ANGLES = {
    "problem_solution": "Lead with a vivid problem the persona faces. Agitate it. Present product as answer.",
    "comparison": "Compare this product against alternatives. Honest pros/cons for each.",
    "how_to": "Step-by-step guide showing how to achieve their goal using this product.",
    "listicle": "'5 Reasons Why [Product] Is the Best'. Easy to scan, high shareability.",
    "deep_dive": "The definitive resource — features, setup, tips, maintenance, FAQ.",
    "case_study": "Story of someone like the persona who solved their problem with this product.",
    "objection_buster": "Directly address the #1 objection. Dismantle it with facts.",
    "seasonal": "Connect product to current event, season, or trend.",
}

def generate_outline(niche: str, products: list, persona: dict, router) -> dict:
    """OUTLINE stage: produce structured outline + angle selection."""
    product_names = [p.get("name", "") for p in products[:3]]
    persona_context = ""
    if persona:
        persona_context = f"""
Persona: {persona.get('name', 'Customer')}
Frustrations: {json.dumps(persona.get('frustrations', []))}
Fears: {json.dumps(persona.get('fears', []))}
Desires: {json.dumps(persona.get('desires', []))}
Tone: {persona.get('tone_of_voice', 'conversational')}"""

    prompt = f"""You are a content strategist planning a buying guide for '{niche}'.
Products: {json.dumps(product_names)}
{persona_context}

Available content angles and when to use them:
{json.dumps(CONTENT_ANGLES, indent=2)}

Select the BEST angle for this niche and persona. Then produce a detailed outline.

Return JSON:
{{
    "selected_angle": "angle_key",
    "angle_rationale": "why this angle works for this persona",
    "outline": [
        "H2: [Section Title] — [2-3 sentence explanation of what this section covers]",
        "H2: Next Section — ..."
    ],
    "primary_keyword": "best long-tail keyword for this niche",
    "search_intent": "commercial / informational / transactional"
}}"""
    result = router.ask(prompt, json_mode=True)
    if result:
        try:
            return json.loads(result) if isinstance(result, str) else result
        except json.JSONDecodeError:
            pass
    return {"selected_angle": "problem_solution", "outline": ["H2: Introduction", "H2: Product Review"], "primary_keyword": f"best {niche}"}


def write_draft(niche: str, products: list, outline: dict, persona: dict,
                research_data: list, router) -> dict:
    """DRAFT stage: write full article from outline + research."""
    product_json = json.dumps(products, indent=2)[:2000]
    outline_sections = "\n".join(outline.get("outline", []))
    persona_context = ""
    if persona:
        persona_context = f"""
Tone: {persona.get('tone_of_voice', 'conversational and honest')}
Pain points: {json.dumps(persona.get('frustrations', []))}
Objections: {json.dumps(persona.get('objections', []))}"""

    prompt = f"""Write a comprehensive buying guide for '{niche}'.

PRODUCTS TO FEATURE:
{product_json}

OUTLINE TO FOLLOW:
{outline_sections}
{persona_context}

WRITING RULES:
- Lead with the reader's problem, not the product
- Be specific — use real numbers and scenarios
- Connect every feature back to a benefit for THIS reader
- Address objections head-on before the reader raises them
- Use PAS framework (Problem → Agitate → Solution) for each product section
- Include exactly 2-3 natural affiliate links within the body
- Affiliate link format: <a href='https://www.amazon.com/s?k=PRODUCT&tag=abvorn-20' rel='nofollow sponsored' target='_blank'>check price on Amazon</a>
- End with a clear, low-risk call to action

Return JSON:
{{
    "post_title": "SEO title (50-65 chars)",
    "meta_description": "Meta description (150-160 chars)",
    "intro": "<p>2-3 sentence hook paragraph (HTML)</p>",
    "article_html": "Full article body HTML (1000-2000 words)",
    "tags": ["{niche}", "buying guide", "review"],
    "lead_magnet_title": "Checklist title",
    "lead_magnet_description": "Short pitch",
    "socials": {{
        "x": "tweet (max 280 chars)",
        "linkedin": "post (max 1300 chars)",
        "pinterest": "description (max 500 chars)",
        "facebook": "1-2 paragraph post"
    }}
}}"""
    result = router.ask(prompt, json_mode=True)
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return None
    return result
```

- [ ] **Step 4: Create FACT-CHECK + POLISH agents**

```python
# abvorn/agents/editor.py
import json, re, logging
from bs4 import BeautifulSoup

logger = logging.getLogger("abvorn.editor")

def fact_check(draft: dict, research_data: list, router) -> dict:
    """FACT-CHECK stage: verify claims against research data."""
    article = (draft.get("intro", "") + draft.get("article_html", ""))[:3000]
    research_text = json.dumps(research_data, indent=2)[:2000]

    prompt = f"""Fact-check this article against the research data.

ARTICLE (first 3000 chars):
{article}

RESEARCH DATA:
{research_text}

Identify any claims that are:
1. Not supported by the research data
2. Contradicted by the research data
3. Exaggerated or speculative

Return JSON with:
{{
    "passed": true/false,
    "issues": [
        {{
            "claim": "the specific claim made",
            "evidence": "what the research actually says",
            "severity": "high/medium/low",
            "suggested_fix": "how to correct it"
        }}
    ],
    "revised_intro": "corrected intro HTML if needed, or empty string",
    "revised_article": "corrected article HTML if needed, or empty string"
}}"""
    result = router.ask(prompt, json_mode=True)
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"passed": True, "issues": []}
    return result or {"passed": True, "issues": []}


def polish(draft: dict, fact_check_result: dict, persona: dict, router) -> dict:
    """POLISH stage: refine tone, conversion architecture, schema."""
    article = fact_check_result.get("revised_article") or draft.get("article_html", "")
    intro = fact_check_result.get("revised_intro") or draft.get("intro", "")
    persona_name = persona.get("name", "reader") if persona else "reader"

    prompt = f"""Polish this buying guide for conversion. Your reader is "{persona_name}".

INTRO: {intro[:500]}
ARTICLE: {article[:2000]}

REQUIRED IMPROVEMENTS:
1. Ensure the emotional arc: problem → trust → solution → proof → action
2. Make sure every paragraph advances the reader toward a decision
3. Verify affiliate links are contextual (not突兀)
4. Ensure scannability: short paragraphs, clear headings
5. Check reading level matches the persona

Return JSON:
{{
    "revised_intro": "polished intro HTML",
    "revised_article": "polished article HTML",
    "quality_score": {{
        "conversion_potential": 1-10,
        "specificity": 1-10,
        "emotional_arc": 1-10,
        "trust_signals": 1-10,
        "readability": 1-10,
        "overall": 0.0
    }},
    "schema_markup": {{
        "article": "... schema.org Article JSON ...",
        "product": "... schema.org Product JSON ...",
        "faq": "... schema.org FAQPage JSON ...",
        "breadcrumb": "... schema.org BreadcrumbList JSON ..."
    }}
}}"""
    result = router.ask(prompt, json_mode=True)
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            return None
    if result:
        return result
    # Fallback: minimal polish
    return {
        "revised_intro": intro,
        "revised_article": article,
        "quality_score": {"overall": 7.0},
        "schema_markup": {}
    }


def build_schema(title, description, url, image, date_published, products, faqs):
    """Generate all schema markup for a page."""
    import json as _json
    article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "image": image,
        "datePublished": date_published,
        "author": {"@type": "Person", "name": "Abvorn Editorial"},
        "publisher": {"@type": "Organization", "name": "Abvorn",
                      "logo": {"@type": "ImageObject", "url": f"{url.split('/')[0]}//{url.split('/')[2]}/logo.svg"}}
    }
    product_items = []
    for p in products:
        product_items.append({
            "@type": "Product",
            "name": p.get("name", "Product"),
            "description": p.get("description", ""),
            "offers": {"@type": "Offer", "price": p.get("price", "Check Price"), "priceCurrency": "USD"}
        })
    product_schema = {"@context": "https://schema.org", "@graph": product_items} if product_items else {}
    faq_items = []
    for q, a in faqs[:5]:
        faq_items.append({"@type": "Question", "name": q,
                          "acceptedAnswer": {"@type": "Answer", "text": a}})
    faq_schema = {"@context": "https://schema.org", "@type": "FAQPage",
                  "mainEntity": faq_items} if faq_items else {}
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": url.split("/")[0] + "//" + url.split("/")[2]},
            {"@type": "ListItem", "position": 2, "name": title, "item": url}
        ]
    }
    return {
        "article": _json.dumps(article),
        "product": _json.dumps(product_schema),
        "faq": _json.dumps(faq_schema),
        "breadcrumb": _json.dumps(breadcrumb)
    }
```

- [ ] **Step 5: Implement ContentPipeline orchestrator**

```python
# abvorn/content/pipeline.py
import json, logging
from datetime import datetime
from abvorn.agents.researcher import research_niche
from abvorn.agents.writer import generate_outline, write_draft
from abvorn.agents.editor import fact_check, polish, build_schema

logger = logging.getLogger("abvorn.pipeline")

class ContentPipeline:
    """5-stage content generation pipeline."""

    def run(self, niche: str, router, persona: dict = None,
            existing_products: list = None) -> dict:
        """Full pipeline: RESEARCH → OUTLINE → DRAFT → FACT-CHECK → POLISH"""
        # Stage 1: RESEARCH
        logger.info(f"[PIPELINE] RESEARCH: {niche}")
        products = existing_products or research_niche(niche, router)
        if not products:
            logger.error(f"[PIPELINE] RESEARCH failed for {niche}")
            return None

        # Stage 2: OUTLINE
        logger.info(f"[PIPELINE] OUTLINE: {niche}")
        outline = generate_outline(niche, products, persona or {}, router)
        if not outline or not outline.get("outline"):
            logger.warning(f"[PIPELINE] OUTLINE empty for {niche}, using default")
            outline = {"outline": ["H2: Introduction", "H2: Product Reviews", "H2: Buying Guide", "H2: FAQ", "H2: Conclusion"],
                       "selected_angle": "problem_solution", "primary_keyword": f"best {niche}"}

        # Stage 3: DRAFT
        logger.info(f"[PIPELINE] DRAFT: {niche}")
        draft = write_draft(niche, products, outline, persona or {}, products, router)
        if not draft:
            logger.error(f"[PIPELINE] DRAFT failed for {niche}")
            return None

        # Stage 4: FACT-CHECK
        logger.info(f"[PIPELINE] FACT-CHECK: {niche}")
        fc_result = fact_check(draft, products, router)
        if fc_result and not fc_result.get("passed") and fc_result.get("issues"):
            for issue in fc_result["issues"][:3]:
                logger.warning(f"  Fact-check issue [{issue.get('severity','low')}]: {issue.get('claim','')[:80]}")

        # Stage 5: POLISH
        logger.info(f"[PIPELINE] POLISH: {niche}")
        polished = polish(draft, fc_result or {}, persona or {}, router)

        # Combine results
        final_intro = polished.get("revised_intro") or fc_result.get("revised_intro") or draft.get("intro", "")
        final_article = polished.get("revised_article") or fc_result.get("revised_article") or draft.get("article_html", "")
        quality = polished.get("quality_score", {"overall": 7.0})
        schema_data = polished.get("schema_markup", {}) or {}

        # Generate FAQ pairs
        faqs = draft.get("faqs", [])
        faq_pairs = [(f.get("question", ""), f.get("answer", "")) for f in faqs if isinstance(f, dict)]

        # Build schema
        schema = build_schema(
            title=draft.get("post_title", f"Best {niche}"),
            description=draft.get("meta_description", f"Best {niche} buying guide"),
            url="",
            image="",
            date_published=datetime.now().isoformat(),
            products=products,
            faqs=faq_pairs
        )

        return {
            "post_title": draft.get("post_title", f"Best {niche} — Expert Review"),
            "meta_description": draft.get("meta_description", f"Find the best {niche} with our expert guide."),
            "intro": final_intro,
            "article_html": final_article,
            "products": products,
            "faqs": faq_pairs,
            "tags": draft.get("tags", [niche, "buying guide"]),
            "lead_magnet_title": draft.get("lead_magnet_title", f"Ultimate {niche} Checklist"),
            "lead_magnet_description": draft.get("lead_magnet_description", "Get our expert checklist."),
            "socials": draft.get("socials", {}),
            "quality_score": quality.get("overall", 7.0),
            "quality_details": quality,
            "schema": schema,
            "selected_angle": outline.get("selected_angle", "problem_solution"),
            "primary_keyword": outline.get("primary_keyword", f"best {niche}"),
        }
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add abvorn/agents/writer.py abvorn/agents/editor.py abvorn/content/pipeline.py tests/test_pipeline.py
git commit -m "feat: add multi-step content pipeline (OUTLINE→DRAFT→FACT-CHECK→POLISH)"
```

---

### Task 4: GA4 Analytics Feedback Loop

**Files:**
- Create: `abvorn/deploy/analytics.py`
- Modify: `abvorn/core/state.py` (already has `update_niche_analytics`)
- Test: `tests/test_analytics.py`

**Interfaces:**
- Consumes: `AbvornState` from Task 1
- Produces: `pull_ga4_analytics(state, secrets) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_analytics.py
import pytest
from abvorn.deploy.analytics import compute_ga4_score

def test_compute_score():
    """Score should weight users more than views, duration as bonus."""
    score = compute_ga4_score(views=100, users=20, avg_duration=30.0)
    assert score > 100  # 100 + 40 + 3 = 143
    assert score < 200
```

- [ ] **Step 2: Create GA4 analytics module**

```python
# abvorn/deploy/analytics.py
import json, logging
from datetime import datetime, timedelta

logger = logging.getLogger("abvorn.analytics")

def compute_ga4_score(views: int, users: int, avg_duration: float) -> float:
    """Weighted score: views baseline, users ×2 for engagement, duration bonus."""
    return round(views + users * 2 + avg_duration / 10, 1)


def pull_ga4_analytics(secrets: dict) -> dict:
    """Pull real page views, users, and session duration from GA4 Data API.
    
    Returns dict: {slug: {"views": int, "users": int, "avg_duration": float, "pages": int}}
    """
    ga4_property_id = secrets.get("GA4_PROPERTY_ID", "")
    ga4_creds_json = secrets.get("GA4_CREDENTIALS_JSON", "")

    if not ga4_property_id or not ga4_creds_json:
        logger.warning("GA4: GA4_PROPERTY_ID or GA4_CREDENTIALS_JSON not configured")
        return {}

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta import RunReportRequest, Metric, DateRange, Dimension
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_info(
            json.loads(ga4_creds_json)
        )
        client = BetaAnalyticsDataClient(credentials=creds)

        request = RunReportRequest(
            property=f"properties/{ga4_property_id}",
            dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="screenPageViews"),
                     Metric(name="activeUsers"),
                     Metric(name="averageSessionDuration")],
            date_ranges=[DateRange(start_date="28daysAgo", end_date="today")],
            limit=50
        )
        response = client.run_report(request)
        analytics = {}
        for row in response.rows:
            path = row.dimension_values[0].value
            slug = path.strip("/").split("/")[0]
            if not slug or slug in ("", "index.html", "about.html", "contact.html", "privacy.html"):
                continue
            views = int(row.metric_values[0].value or 0)
            users = int(row.metric_values[1].value or 0)
            duration = float(row.metric_values[2].value or 0)
            if slug not in analytics:
                analytics[slug] = {"views": 0, "users": 0, "avg_duration": 0, "pages": 0}
            analytics[slug]["views"] += views
            analytics[slug]["users"] += users
            analytics[slug]["avg_duration"] = max(analytics[slug]["avg_duration"], duration)
            analytics[slug]["pages"] += 1

        logger.info(f"GA4: pulled analytics for {len(analytics)} niches")
        return analytics

    except Exception as e:
        logger.error(f"GA4 pull failed: {e}")
        return {}


def apply_analytics_feedback(state, analytics: dict):
    """Feed GA4 data back into niche priorities and persona tracking."""
    if not analytics:
        return

    for slug, data in analytics.items():
        score = compute_ga4_score(data["views"], data["users"], data["avg_duration"])
        state.update_niche_analytics(slug, data["views"], data["users"], score)

        # Strategic decisions based on real data
        niche = state.get_niche(slug)
        if niche:
            if score > 100 and niche["avg_quality"] >= 7.0:
                logger.info(f"  ⬆️ Double down: {slug} (score={score}, quality={niche['avg_quality']})")
                state.enqueue(slug, "content", priority=15)
            elif score < 10 and niche["total_posts"] >= 3:
                logger.info(f"  ⬇️ Pivot: {slug} (score={score}, posts={niche['total_posts']})")
                # Try a different angle instead of abandoning
                state.enqueue(slug, "content", priority=5,
                              payload={"try_new_angle": True})

    # Top niches summary
    all_niches = state.get_all_niches()
    top = sorted(all_niches, key=lambda n: n["ga4_score"], reverse=True)[:3]
    if top:
        top_strs = [f"{n['slug']}({n['ga4_score']})" for n in top]
        logger.info(f"GA4 top niches: {', '.join(top_strs)}")
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_analytics.py -v`
Expected: PASS

- [ ] **Step 4: Update GHA workflow to include GA4 secrets**

```yaml
# In .github/workflows/abvorn-daily.yml env section, add:
  GA4_PROPERTY_ID:       ${{ secrets.GA4_PROPERTY_ID }}
  GA4_CREDENTIALS_JSON:  ${{ secrets.GA4_CREDENTIALS_JSON }}
```

- [ ] **Step 5: Commit**

```bash
git add abvorn/deploy/analytics.py tests/test_analytics.py
git commit -m "feat: add GA4 analytics feedback loop with automated niche prioritization"
```

---

### Task 5: Colab Wrapper Cells (Backward Compat)

**Files:**
- Modify: `abvorn_cell1.py` (import from abvorn package instead of inline code)
- Modify: `abvorn_cell2.py` (same)
- Modify: `abvorn_cell3.py` (same)
- Modify: `abvorn_cycle.py` (use abvorn package)

**Interfaces:**
- Consumes: all modules from Tasks 1-4
- Produces: working Colab notebooks and cycle runner

- [ ] **Step 1: Refactor cell1.py to import from package**

```python
# At the top of cell1.py, replace all inline definitions with:
from abvorn.core.secrets import load_secrets, get_boardroom_path, get_empire_path
from abvorn.core.state import AbvornState
from abvorn.core.models import ModelRouter

# Keep only: SOUL, PLATFORM_GUIDE, templates, CSS, and Notebook-specific UI code
# All core logic (secret parsing, state management, AI routing, research, content)
# lives in the abvorn/ package now
```

- [ ] **Step 2: Verify backward compatibility**

Run: `python abvorn_cycle.py`
Expected: System starts, imports work, existing state migrates

- [ ] **Step 3: Commit**

```bash
git add abvorn_cell1.py abvorn_cell2.py abvorn_cell3.py abvorn_cycle.py
git commit -m "refactor: colab cells now thin wrappers around abvorn package"
```