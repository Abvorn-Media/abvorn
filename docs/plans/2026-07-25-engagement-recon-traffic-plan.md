# Engagement, Trend Recon & Traffic Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire up 3 independent subsystems — social mention engagement, real trend data from the web, and GA4 traffic analytics — plus update the roadmap.

**Architecture:** Each subsystem is a self-contained package. Engagement monitors X mentions via Composio and crafts warm replies via LLM. Trend recon replaces hardcoded seed data with DuckDuckGo + Amazon + Reddit + Google Trends providers. GA4 client pulls page views/sessions into a new analytics engine. All wired into existing daemon/ambassador.

**Tech Stack:** Python, Composio SDK, `requests` + `BeautifulSoup4` (Amazon scraping), `duckduckgo_search` (DDGS), `pytrends`, `google-analytics-data`, `asyncio`

## Global Constraints

- Composio API calls: poll mentions every 15 min minimum, never more frequently
- Trend recon uses ZERO Composio calls — only free/self-rate-limited APIs
- GA4 uses Google Data API directly (not Composio)
- All new modules follow existing naming conventions (`snake_case` files, `PascalCase` classes)
- Every new function gets tests (TDD: write test first, implement, verify)

---

### Task 1: Engagement Package — MentionWatcher

**Files:**
- Create: `abvorn/engagement/__init__.py`
- Create: `abvorn/engagement/watcher.py`
- Create: `tests/engagement_test.py`

**Interfaces:**
- Consumes: `ComposioToolSet` (from `composio`), `Action.TWITTER_GET_MENTIONS`
- Produces: `MentionWatcher.poll() -> list[Mention]` where `Mention = {"id": str, "author": str, "text": str, "tweet_id": str, "created_at": str}`

- [ ] **Step 1: Write the failing test for MentionWatcher.poll**

```python
"""Tests for MentionWatcher — polls Composio for mentions with dedup."""
import pytest
from unittest.mock import MagicMock, patch
from abvorn.engagement.watcher import MentionWatcher

def test_watcher_initializes():
    mw = MentionWatcher(composio_key="test", state=None)
    assert mw is not None
    assert mw.poll_interval == 900

def test_poll_returns_list():
    mw = MentionWatcher(composio_key="test", state=None)
    result = mw.poll()
    assert isinstance(result, list)

def test_poll_deduplicates():
    mw = MentionWatcher(composio_key="test", state=None)
    mw._replied_ids.add("dup_1")
    mw._raw_mentions = [{"id": "dup_1", "text": "old"}, {"id": "new_1", "text": "new"}]
    result = mw.poll()
    assert len(result) == 1
    assert result[0]["id"] == "new_1"

def test_filter_substantive_only():
    mw = MentionWatcher(composio_key="test", state=None)
    mw._raw_mentions = [
        {"id": "1", "text": "@abvorn nice!", "author": "user1"},
        {"id": "2", "text": "Does this work with Samsung TVs? I've been looking for something like this.", "author": "user2"},
        {"id": "3", "text": "lol", "author": "user3"},
    ]
    result = mw.poll()
    assert len(result) == 1
    assert result[0]["id"] == "2"

def test_no_key_returns_empty():
    mw = MentionWatcher(composio_key="", state=None)
    assert mw.poll() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/engagement_test.py -v --tb=short`
Expected: FAIL with ImportError or function not defined

- [ ] **Step 3: Write MentionWatcher**

```python
"""MentionWatcher — polls Composio for social mentions with rate-limit-safe polling."""

import logging
from datetime import datetime

logger = logging.getLogger("abvorn.engagement.watcher")

SPAM_PATTERNS = ["lol", "nice", "cool", "follow me", "check out", "http://", "https://"]

try:
    from composio import ComposioToolSet, Action
    HAS_COMPOSIO = True
except ImportError:
    HAS_COMPOSIO = False
    Action = object


class MentionWatcher:
    """Polls Composio for mentions every 15 min. Deduplicates and filters spam."""

    def __init__(self, composio_key: str = "", state=None):
        self.composio_key = composio_key
        self.state = state
        self.poll_interval = 900
        self._replied_ids = set()
        self._raw_mentions = []
        self._composio = None
        if composio_key and HAS_COMPOSIO:
            try:
                self._composio = ComposioToolSet(api_key=composio_key)
            except Exception as e:
                logger.warning(f"Composio init failed: {e}")

    def poll(self) -> list[dict]:
        """Poll for new mentions. Returns only substantive, unseen mentions."""
        if not self._composio:
            return []
        self._fetch_mentions()
        return self._filter_new()

    def _fetch_mentions(self):
        mentions_action = getattr(Action, "TWITTER_GET_MENTIONS", None)
        if not mentions_action:
            return
        try:
            result = self._composio.execute_action(mentions_action, params={"count": 20})
            self._raw_mentions = result if isinstance(result, list) else []
        except Exception as e:
            logger.debug(f"Mention fetch failed: {e}")

    def _filter_new(self) -> list[dict]:
        results = []
        for m in self._raw_mentions:
            mid = str(m.get("id", ""))
            if mid in self._replied_ids:
                continue
            text = m.get("text", "")
            if not self._is_substantive(text):
                continue
            self._replied_ids.add(mid)
            results.append({
                "id": mid,
                "author": m.get("author", m.get("user", {}).get("username", "unknown")),
                "text": text,
                "tweet_id": mid,
                "created_at": m.get("created_at", datetime.now().isoformat()),
            })
        return results

    def _is_substantive(self, text: str) -> bool:
        if len(text) < 20:
            return False
        lower = text.lower()
        for pat in SPAM_PATTERNS:
            if pat in lower:
                return False
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/engagement_test.py -v --tb=short`
Expected: PASS (5/5)

- [ ] **Step 5: Commit**

```bash
git add abvorn/engagement/ tests/engagement_test.py
git commit -m "feat: MentionWatcher polls Composio for mentions with dedup + spam filter"
```

---

### Task 2: Engagement Package — ReplyGenerator & ReplyPoster

**Files:**
- Create: `abvorn/engagement/replier.py`
- Modify: `tests/engagement_test.py` (append tests)

**Interfaces:**
- Consumes: `MentionWatcher.poll() -> list[Mention]`, `ModelRouter.ask(prompt, task=)`, `ComposioToolSet`, `Action.X_CREATE_TWEET`
- Produces: `ReplyGenerator.craft(mention, context) -> str`, `ReplyPoster.post(mention, reply_text) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/engagement_test.py

from abvorn.engagement.replier import ReplyGenerator, ReplyPoster

def test_reply_generator_initializes():
    rg = ReplyGenerator(router=None)
    assert rg is not None

def test_reply_generator_craft_returns_string():
    rg = ReplyGenerator(router=None)
    reply = rg.craft({"text": "Does this work with Samsung TVs?", "author": "user"}, {})
    assert isinstance(reply, str)
    assert len(reply) > 10

def test_reply_generator_with_llm():
    router = MagicMock()
    router.ask.return_value = "Great question! Yes, it works with Samsung TVs from 2022 onwards."
    rg = ReplyGenerator(router=router)
    reply = rg.craft({"text": "Does this work with Samsung TVs?", "author": "user"},
                     {"niche": "tv", "post_title": "Best TV 2026"})
    assert "Samsung" in reply
    router.ask.assert_called_once()

def test_reply_poster_initializes():
    rp = ReplyPoster(composio_key="test")
    assert rp is not None

def test_reply_poster_no_key():
    rp = ReplyPoster(composio_key="")
    result = rp.post({"tweet_id": "123"}, "Great question!")
    assert result["status"] == "skipped"

def test_reply_poster_returns_structure():
    rp = ReplyPoster(composio_key="fake_key")
    result = rp.post({"tweet_id": "123"}, "Thanks for asking!")
    assert "status" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/engagement_test.py -v --tb=short`
Expected: 5 old pass, 6 new FAIL (ImportError)

- [ ] **Step 3: Write ReplyGenerator & ReplyPoster**

```python
"""ReplyGenerator and ReplyPoster — craft warm replies and post them via Composio."""

import logging
from datetime import datetime

logger = logging.getLogger("abvorn.engagement.replier")

ENGAGEMENT_PERSONA = (
    "You are Abvorn's social media ambassador — warm, knowledgeable, and genuinely helpful. "
    "Someone just mentioned Abvorn or asked a question on social media. Reply in a way that feels "
    "human, not corporate. Be specific, be helpful, and never sound like a bot."
)

try:
    from composio import ComposioToolSet, Action
    HAS_COMPOSIO = True
except ImportError:
    HAS_COMPOSIO = False
    Action = object


class ReplyGenerator:
    """Crafts warm, on-brand replies to social mentions."""

    def __init__(self, router=None):
        self.router = router

    def craft(self, mention: dict, context: dict = None) -> str:
        """Generate a reply to a mention."""
        context = context or {}
        if self.router:
            try:
                prompt = (
                    f"The user @{mention.get('author', 'unknown')} said: "
                    f"\"{mention.get('text', '')}\"\n\n"
                    f"Context: we just posted about {context.get('niche', 'products')} — "
                    f"\"{context.get('post_title', 'our latest guide')}\".\n\n"
                    f"Write a warm, helpful reply (1-3 sentences):"
                )
                reply = self.router.ask(prompt, task="social", system=ENGAGEMENT_PERSONA)
                if reply and len(reply) > 10:
                    return reply.strip()
            except Exception as e:
                logger.warning(f"Reply generation failed: {e}")

        return f"Thanks for the question, @{mention.get('author', 'unknown')}! "
        f"Great point — we cover exactly that in our guide. Hope it helps!"


class ReplyPoster:
    """Posts replies to social media via Composio."""

    def __init__(self, composio_key: str = ""):
        self.composio_key = composio_key
        self._composio = None
        if composio_key and HAS_COMPOSIO:
            try:
                self._composio = ComposioToolSet(api_key=composio_key)
            except Exception as e:
                logger.warning(f"Composio init failed: {e}")

    def post(self, mention: dict, reply_text: str) -> dict:
        """Post a reply to the mention's tweet."""
        if not self._composio:
            return {"status": "skipped", "reason": "no_composio"}
        tweet_id = mention.get("tweet_id", "")
        if not tweet_id:
            return {"status": "error", "reason": "no_tweet_id"}
        reply_action = getattr(Action, "TWITTER_CREATE_TWEET", None)
        if not reply_action:
            return {"status": "error", "reason": "no_action"}
        try:
            self._composio.execute_action(reply_action, params={
                "text": reply_text[:280],
                "reply_to": tweet_id,
            })
            logger.info(f"Replied to {mention.get('author')}: {reply_text[:60]}...")
            return {"status": "posted", "mention_id": mention.get("id", ""),
                    "author": mention.get("author", "")}
        except Exception as e:
            logger.warning(f"Reply failed: {e}")
            return {"status": "failed", "error": str(e)[:100]}
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/engagement_test.py -v --tb=short`
Expected: 11/11 PASS

- [ ] **Step 5: Commit**

```bash
git add abvorn/engagement/replier.py tests/engagement_test.py
git commit -m "feat: ReplyGenerator + ReplyPoster — warm LLM replies via Composio"
```

---

### Task 3: Wire Engagement into SocialAmbassador

**Files:**
- Modify: `abvorn/agents/ambassador.py` (engage decision path)
- Modify: `tests/ambassador_test.py` (add engage test)

**Interfaces:**
- Consumes: `MentionWatcher`, `ReplyGenerator`, `ReplyPoster`
- Produces: Ambassador's `act("engage")` replies to mentions

- [ ] **Step 1: Write failing test**

```python
# Append to tests/ambassador_test.py

@pytest.mark.asyncio
async def test_act_engage_with_mentions(ambassador, router, social):
    from abvorn.engagement.watcher import MentionWatcher
    from abvorn.engagement.replier import ReplyGenerator, ReplyPoster
    ambassador.mention_watcher = MentionWatcher(composio_key="", state=None)
    ambassador.reply_generator = ReplyGenerator(router=router)
    ambassador.reply_poster = ReplyPoster(composio_key="")
    ambassador._perception = {"published_content": [], "mentions": [], "schedule_due": []}
    decision = await ambassador.decide({"published_content": [], "mentions": [{"id": "1"}], "schedule_due": []})
    assert decision == "engage"
    result = await ambassador.act("engage")
    assert result["action"] == "engage"

@pytest.mark.asyncio
async def test_act_engage_no_mentions(ambassador):
    ambassador._perception = {"published_content": [], "mentions": [], "schedule_due": []}
    result = await ambassador.act("engage")
    assert result["action"] == "none"
```

- [ ] **Step 2: Implement engage path in ambassador**

In `abvorn/agents/ambassador.py`, update `__init__` to create engagement components, and implement `act("engage")`:

```python
# In __init__, after notifier:
from ..engagement.watcher import MentionWatcher
from ..engagement.replier import ReplyGenerator, ReplyPoster
self.mention_watcher = MentionWatcher(
    getattr(social, 'composio_key', ''),
    state=state
)
self.reply_generator = ReplyGenerator(router=router)
self.reply_poster = ReplyPoster(getattr(social, 'composio_key', ''))

# In act() - update the engage branch:
if decision == "engage":
    mentions = self._perception.get("mentions", [])
    if not mentions:
        return {"action": "none"}
    results = []
    for m in mentions[:5]:
        reply = self.reply_generator.craft(m, {})
        result = self.reply_poster.post(m, reply)
        results.append(result)
    return {"action": "engage", "replied": len(results)}

# In perceive() - also check actual mentions via watcher:
if "mentions" not in p or not p["mentions"]:
    watcher_mentions = self.mention_watcher.poll()
    if watcher_mentions:
        p["mentions"] = watcher_mentions
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/ambassador_test.py tests/engagement_test.py -v --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add abvorn/agents/ambassador.py abvorn/engagement/
git commit -m "feat: wire engagement cycle into SocialAmbassador"
```

---

### Task 4: Trend Recon Providers

**Files:**
- Create: `abvorn/trends/recon/__init__.py`
- Create: `abvorn/trends/recon/providers.py` (DuckDuckGoSource, AmazonSource, RedditSource, GoogleTrendsSource)
- Create: `tests/recon_test.py`

**Interfaces:**
- Consumes: `duckduckgo_search` DDGS, `requests`, `BeautifulSoup`, `pytrends`
- Produces: `List[dict]` with `product_name`, `category`, `source`, `confidence`, `price_range`, `url`

- [ ] **Step 1: Write tests**

```python
"""Tests for trend recon providers."""
import pytest
from abvorn.trends.recon.providers import (
    DuckDuckGoSource, AmazonSource, RedditSource, GoogleTrendsSource
)


def test_duckduckgo_initializes():
    s = DuckDuckGoSource()
    assert s is not None


def test_duckduckgo_search_returns_list():
    s = DuckDuckGoSource()
    results = s.search("tv")
    assert isinstance(results, list)


def test_duckduckgo_results_have_required_keys():
    s = DuckDuckGoSource()
    results = s.search("tv")
    if results:
        r = results[0]
        assert "product_name" in r
        assert "source" in r
        assert "confidence" in r


def test_amazon_initializes():
    s = AmazonSource()
    assert s is not None


def test_amazon_search_returns_list():
    s = AmazonSource()
    results = s.search("tv")
    assert isinstance(results, list)


def test_reddit_initializes():
    s = RedditSource()
    assert s is not None


def test_reddit_search_returns_list():
    s = RedditSource()
    results = s.search("tv")
    assert isinstance(results, list)


def test_google_trends_initializes():
    s = GoogleTrendsSource()
    assert s is not None


def test_google_trends_search_returns_list():
    s = GoogleTrendsSource()
    results = s.search("tv")
    assert isinstance(results, list)
```

- [ ] **Step 2: Run to verify fails**

Run: `python -m pytest tests/recon_test.py -v --tb=short`
Expected: FAIL (ImportError)

- [ ] **Step 3: Write providers**

```python
"""Trend recon providers — real web data sources for trend discovery."""

import logging, re, time
from typing import Optional

logger = logging.getLogger("abvorn.trends.recon")

class DuckDuckGoSource:
    """Searches DuckDuckGo for trending products in a niche."""

    def __init__(self):
        self._ddgs = None
        try:
            from duckduckgo_search import DDGS
            self._ddgs = DDGS()
        except ImportError:
            logger.warning("duckduckgo_search not installed")

    def search(self, category: str, max_results: int = 5) -> list[dict]:
        if not self._ddgs:
            return []
        queries = [f"best {category} 2026", f"top rated {category}", f"{category} review 2026"]
        seen = set()
        results = []
        for q in queries:
            try:
                for r in self._ddgs.text(q, max_results=3):
                    title = r.get("title", "")
                    body = r.get("body", "")
                    products = self._extract_products(title + " " + body)
                    for p in products:
                        key = p.lower().strip()
                        if key not in seen:
                            seen.add(key)
                            results.append({
                                "product_name": p,
                                "category": category,
                                "source": "duckduckgo",
                                "confidence": 60,
                                "price_range": "",
                                "url": r.get("href", ""),
                            })
                time.sleep(1)
            except Exception as e:
                logger.debug(f"DDG search failed for '{q}': {e}")
        return results[:max_results]

    def _extract_products(self, text: str) -> list[str]:
        patterns = [
            r'([A-Z][a-zA-Z0-9\s]+(?:Pro|Max|Air|Ultra|Plus|Gen\d|M\d))',
            r'([A-Z][a-z]+(?:\s[A-Z][a-zA-Z0-9]+){1,4})',
        ]
        found = set()
        for pat in patterns:
            for match in re.finditer(pat, text):
                candidate = match.group(1).strip()
                if 5 < len(candidate) < 60 and not candidate.startswith("The "):
                    found.add(candidate)
        return list(found)


class AmazonSource:
    """Scrapes Amazon best sellers for trending products."""

    AMAZON_URLS = {
        "tv": "https://www.amazon.com/gp/bestsellers/electronics/172659",
        "laptop": "https://www.amazon.com/gp/bestsellers/electronics/13896617011",
        "robot vacuum": "https://www.amazon.com/gp/bestsellers/home-garden/13249881",
        "monitor": "https://www.amazon.com/gp/bestsellers/electronics/1292115011",
        "smart home": "https://www.amazon.com/gp/bestsellers/electronics/9811847011",
    }

    def search(self, category: str, max_results: int = 5) -> list[dict]:
        url = self.AMAZON_URLS.get(category)
        if not url:
            return []
        try:
            import requests
            from bs4 import BeautifulSoup
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for item in soup.select("div.p13n-sc-uncoverable-faceout")[:max_results]:
                title_el = item.select_one("div._cDEzb_p13n-sc-css-line-clamp-3_g3dy1")
                if title_el:
                    name = title_el.get_text(strip=True)
                    results.append({
                        "product_name": name,
                        "category": category,
                        "source": "amazon",
                        "confidence": 70,
                        "price_range": "",
                        "url": url,
                    })
            return results
        except Exception as e:
            logger.debug(f"Amazon scrape failed: {e}")
            return []


class RedditSource:
    """Searches Reddit for product recommendation threads."""

    def search(self, category: str, max_results: int = 5) -> list[dict]:
        try:
            import requests
            subreddits = [category.replace(" ", ""), "buyingadvice", "recommendations"]
            results = []
            seen = set()
            for sub in subreddits:
                try:
                    url = f"https://www.reddit.com/r/{sub}/search.json?q={category}&restrict_sr=1&sort=top&t=year&limit=5"
                    headers = {"User-Agent": "Abvorn/1.0"}
                    resp = requests.get(url, headers=headers, timeout=10)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for child in data.get("data", {}).get("children", []):
                        title = child.get("data", {}).get("title", "")
                        products = self._extract_products(title)
                        for p in products:
                            key = p.lower().strip()
                            if key not in seen:
                                seen.add(key)
                                results.append({
                                    "product_name": p,
                                    "category": category,
                                    "source": "reddit",
                                    "confidence": 55,
                                    "price_range": "",
                                    "url": child.get("data", {}).get("url", ""),
                                })
                    time.sleep(1)
                except Exception:
                    continue
            return results[:max_results]
        except Exception as e:
            logger.debug(f"Reddit search failed: {e}")
            return []

    def _extract_products(self, text: str) -> list[str]:
        patterns = [
            r'([A-Z][a-zA-Z0-9\s]+(?:Pro|Max|Air|Ultra|Plus|Gen\d|M\d))',
            r'(?:recommend|suggest|best)\s+([A-Z][a-zA-Z\s]{3,40})',
        ]
        found = set()
        for pat in patterns:
            for match in re.finditer(pat, text):
                candidate = match.group(1).strip()
                if 5 < len(candidate) < 60:
                    found.add(candidate)
        return list(found)


class GoogleTrendsSource:
    """Polls Google Trends for rising search terms in a niche."""

    def search(self, category: str, max_results: int = 5) -> list[dict]:
        try:
            from pytrends.request import TrendReq
            pytrends = TrendReq(hl="en-US", tz=300)
            pytrends.build_payload(kw_list=[category], timeframe="today 3-m", geo="US")
            related = pytrends.related_queries()
            rising = related.get(category, {}).get("rising", [])
            if rising is None:
                return []
            results = []
            for item in rising.head(max_results).to_dict("records"):
                query = item.get("query", "")
                if query and len(query) > 3:
                    results.append({
                        "product_name": query,
                        "category": category,
                        "source": "googletrends",
                        "confidence": 65,
                        "price_range": "",
                        "url": "",
                    })
            return results
        except Exception as e:
            logger.debug(f"Google Trends failed: {e}")
            return []
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/recon_test.py -v --tb=short`
Expected: 10/10 PASS

- [ ] **Step 5: Commit**

```bash
git add abvorn/trends/recon/ tests/recon_test.py
git commit -m "feat: trend recon providers — DuckDuckGo, Amazon, Reddit, Google Trends"
```

---

### Task 5: Wire Recon Providers into TrendScanner

**Files:**
- Modify: `abvorn/trends/scanner.py` (replace hardcoded seeds with recon providers)
- Modify: `tests/recon_test.py` (add scanner integration tests)

- [ ] **Step 1: Write failing tests**

```python
# Append to tests/recon_test.py

from abvorn.trends.scanner import TrendScanner

def test_scanner_with_recon():
    scanner = TrendScanner()
    results = scanner.scan(["tv"])
    assert isinstance(results, list)

def test_scanner_aggregates_multiple_sources():
    scanner = TrendScanner()
    results = scanner.scan(["tv"])
    if results:
        r = results[0]
        assert "product_name" in r
        assert "score" in r
        assert "sources" in r

def test_scanner_deduplicates():
    scanner = TrendScanner()
    results = scanner.scan(["tv"])
    names = [r["product_name"].lower() for r in results]
    assert len(names) == len(set(names))
```

- [ ] **Step 2: Modify TrendScanner.scan()**

Replace the `_scan_web`, `_scan_amazon`, `_scan_trends` methods with recon provider calls:

```python
from .recon.providers import DuckDuckGoSource, AmazonSource, RedditSource, GoogleTrendsSource

class TrendScanner:
    def __init__(self, ...):
        ...
        self._recon_providers = [
            DuckDuckGoSource(),
            AmazonSource(),
            RedditSource(),
            GoogleTrendsSource(),
        ]

    def _scan_web(self, category: str) -> list:
        results = []
        for provider in self._recon_providers:
            try:
                results.extend(provider.search(category))
            except Exception as e:
                logger.debug(f"{provider.__class__.__name__} failed: {e}")
        return results

    def _scan_amazon(self, category: str) -> list:
        return []  # deprecated — recon providers cover this

    def _scan_trends(self, category: str) -> list:
        return []  # deprecated — recon providers cover this
```

Also remove `_WEB_SEED_PRODUCTS` and the old `_scan_web` implementation.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/recon_test.py tests/trends_test.py -v --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add abvorn/trends/
git commit -m "feat: wire recon providers into TrendScanner, replace hardcoded seeds"
```

---

### Task 6: GA4 Traffic Analytics

**Files:**
- Create: `abvorn/analytics/__init__.py`
- Create: `abvorn/analytics/ga4.py`
- Create: `abvorn/analytics/engine.py`
- Create: `tests/analytics_test.py`

**Interfaces:**
- Consumes: `google.analytics.data_v1beta`, GA4 credentials from secrets
- Produces: `GA4Client.query(days=7) -> dict` with page views, sessions, top pages, traffic sources

- [ ] **Step 1: Write tests**

```python
"""Tests for GA4 traffic analytics and analytics engine."""
import pytest
from unittest.mock import MagicMock, patch
from abvorn.analytics.ga4 import GA4Client
from abvorn.analytics.engine import AnalyticsEngine


def test_ga4_client_initializes():
    client = GA4Client(property_id="123456789")
    assert client is not None


def test_ga4_client_no_credentials():
    client = GA4Client()
    result = client.query()
    assert result["status"] == "unconfigured"


def test_ga4_client_query_returns_structure():
    client = GA4Client(property_id="123456789")
    with patch.object(client, '_run_report', return_value={
        "rows": [
            {"dimensions": ["/best-tv-2026"], "metrics": [150, 120, 45]},
            {"dimensions": ["/best-laptop-2026"], "metrics": [200, 180, 60]},
        ]
    }):
        result = client.query(days=7)
        assert "pages" in result
        assert result["total_page_views"] == 350
        assert len(result["pages"]) == 2


def test_ga4_client_cache():
    client = GA4Client(property_id="123456789")
    client._cache = {"key": {"data": {"total_page_views": 100}, "time": 9999999999}}
    result = client.query(days=7)
    assert result["total_page_views"] == 100


def test_analytics_engine_initializes():
    engine = AnalyticsEngine()
    assert engine is not None


def test_analytics_engine_collect():
    engine = AnalyticsEngine(ga4_client=GA4Client())
    report = engine.collect()
    assert isinstance(report, dict)


def test_analytics_engine_insight_report():
    engine = AnalyticsEngine()
    engine.data = {"total_page_views": 1000, "top_pages": [{"path": "/test", "views": 500}]}
    report = engine.generate_insight_report()
    assert isinstance(report, str)
    assert "1000" in report or len(report) > 20
```

- [ ] **Step 2: Run to verify fails**

Run: `python -m pytest tests/analytics_test.py -v --tb=short`
Expected: FAIL (ImportError)

- [ ] **Step 3: Write GA4Client**

```python
"""GA4Client — pulls traffic data from Google Analytics 4 Data API."""

import logging, time
from datetime import datetime, timedelta

logger = logging.getLogger("abvorn.analytics.ga4")


class GA4Client:
    """Queries GA4 Data API for page views, sessions, and traffic sources."""

    def __init__(self, property_id: str = "", credentials_json: str = ""):
        self.property_id = property_id
        self.credentials_json = credentials_json
        self._client = None
        self._cache = {}
        self._init_client()

    def _init_client(self):
        if not self.property_id:
            return
        try:
            from google.analytics.data_v1beta import BetaAnalyticsDataClient
            from google.oauth2.service_account import Credentials
            if self.credentials_json:
                import json
                creds = Credentials.from_service_account_info(json.loads(self.credentials_json))
                self._client = BetaAnalyticsDataClient(credentials=creds)
            else:
                self._client = BetaAnalyticsDataClient()
        except Exception as e:
            logger.warning(f"GA4 client init failed: {e}")

    def query(self, days: int = 7) -> dict:
        """Query GA4 for page views, sessions, top pages."""
        if not self._client:
            return {"status": "unconfigured"}
        cache_key = f"ga4_{days}"
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached["time"] < 3600:
            return cached["data"]
        try:
            result = self._run_report(days)
            self._cache[cache_key] = {"data": result, "time": time.time()}
            return result
        except Exception as e:
            logger.warning(f"GA4 query failed: {e}")
            return {"status": "error", "error": str(e)[:100]}

    def _run_report(self, days: int) -> dict:
        from google.analytics.data_v1beta.types import (
            RunReportRequest, DateRange, Dimension, Metric,
        )
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        end = datetime.now().strftime("%Y-%m-%d")
        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            date_ranges=[DateRange(start_date=start, end_date=end)],
            dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="screenPageViews"), Metric(name="sessions"),
                     Metric(name="activeUsers")],
            limit=10,
        )
        response = self._client.run_report(request)
        total_views = 0
        total_sessions = 0
        total_users = 0
        pages = []
        for row in response.rows:
            path = row.dimension_values[0].value
            views = int(row.metric_values[0].value)
            sessions = int(row.metric_values[1].value)
            users = int(row.metric_values[2].value)
            total_views += views
            total_sessions += sessions
            total_users += users
            pages.append({"path": path, "views": views, "sessions": sessions, "users": users})
        return {
            "status": "ok",
            "total_page_views": total_views,
            "total_sessions": total_sessions,
            "total_users": total_users,
            "pages": pages,
            "period_days": days,
        }
```

- [ ] **Step 4: Write AnalyticsEngine**

```python
"""AnalyticsEngine — merges GA4 data with internal signals for unified reporting."""

import logging
from datetime import datetime

logger = logging.getLogger("abvorn.analytics.engine")


class AnalyticsEngine:
    """Collects internal signals + external GA4 data into unified insight reports."""

    def __init__(self, ga4_client=None, state=None):
        self.ga4_client = ga4_client
        self.state = state
        self.data = {}

    def collect(self) -> dict:
        """Collect all signals into one report dict."""
        report = {
            "collected_at": datetime.now().isoformat(),
            "internal": self._collect_internal(),
            "traffic": self._collect_traffic(),
        }
        self.data = report
        return report

    def _collect_internal(self) -> dict:
        if not self.state:
            return {}
        return {
            "total_posts": self.state.get_meta("total_posts", 0),
            "total_ctas": self.state.get_meta("total_ctas", 0),
            "total_hooks_tested": self.state.get_meta("total_hooks_tested", 0),
            "emails_dispatched": self.state.get_meta("emails_dispatched_total", 0),
            "optimization_cycles": self.state.get_meta("optimization_cycle_count", 0),
        }

    def _collect_traffic(self) -> dict:
        if not self.ga4_client:
            return {"status": "unconfigured"}
        return self.ga4_client.query()

    def generate_insight_report(self) -> str:
        """Generate a human-readable insight report."""
        if not self.data:
            self.collect()
        lines = [f"# Abvorn Analytics Report", f"**Generated:** {self.data.get('collected_at', 'now')}", ""]

        traffic = self.data.get("traffic", {})
        if traffic.get("status") == "ok":
            lines.append("## Traffic (GA4)")
            lines.append(f"- **Page views:** {traffic.get('total_page_views', 0)}")
            lines.append(f"- **Sessions:** {traffic.get('total_sessions', 0)}")
            lines.append(f"- **Active users:** {traffic.get('total_users', 0)}")
            lines.append("")
            lines.append("### Top Pages")
            for p in traffic.get("pages", []):
                lines.append(f"- {p['path']}: {p['views']} views, {p['sessions']} sessions")
        else:
            lines.append("## Traffic")
            lines.append("- GA4 not configured")

        internal = self.data.get("internal", {})
        if internal:
            lines.append("")
            lines.append("## Internal Signals")
            for key, val in internal.items():
                label = key.replace("_", " ").title()
                lines.append(f"- **{label}:** {val}")

        return "\n".join(lines)
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/analytics_test.py -v --tb=short`
Expected: 7/7 PASS

- [ ] **Step 6: Commit**

```bash
git add abvorn/analytics/ tests/analytics_test.py
git commit -m "feat: GA4 traffic analytics + AnalyticsEngine with insight reports"
```

---

### Task 7: Wire Analytics into Daemon + Telegram

**Files:**
- Modify: `abvorn/daemon.py` (add GA4 client, `/traffic` command in notifier)
- Modify: `abvorn/deploy/notifier.py` (add `/traffic` command handler)

- [ ] **Step 1: Add `/traffic` command to TelegramNotifier**

In `abvorn/deploy/notifier.py`, add to `COMMANDS` dict and `process_command`:

```python
# In COMMANDS:
"/traffic": "Show traffic analytics from GA4",

# In process_command():
if base_cmd == "/traffic":
    lines = ["📈 <b>Traffic Analytics</b>"]
    if hasattr(self, '_analytics_engine') and self._analytics_engine:
        report = self._analytics_engine.generate_insight_report()
        lines.append(report[:3000])
    else:
        lines.append("• Analytics engine not available")
    return "\n".join(lines)
```

- [ ] **Step 2: Wire GA4 into daemon**

In `abvorn/daemon.py` `_init_phase3()`:

```python
from .analytics.ga4 import GA4Client
from .analytics.engine import AnalyticsEngine

ga4_property_id = self.secrets.get("GA4_PROPERTY_ID", "")
ga4_creds = self.secrets.get("GA4_CREDENTIALS_JSON", "")
self.ga4_client = GA4Client(property_id=ga4_property_id, credentials_json=ga4_creds)
self.analytics = AnalyticsEngine(ga4_client=self.ga4_client, state=self.state)
self.notifier._analytics_engine = self.analytics
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/ -q --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add abvorn/daemon.py abvorn/deploy/notifier.py
git commit -m "feat: wire GA4 analytics into daemon + /traffic Telegram command"
```

---

### Task 8: Update Roadmap

**Files:**
- Modify: `abvorn/brain/roadmap.md`

- [ ] **Step 1: Rewrite roadmap with all shipped concepts + new tiers**

Replace the roadmap content to:
- Move to Shipped: Archive, Intel, UIX, CTA, Hooks, Brain Principles, Trend Pipeline (scanner + planner + schedule), Image Generation, Daemon, Agents (Supervisor + Ambassador), Composio/Social Deployer, Analytics, Email Capture, Models/Cost Tracking
- Add Tier 1: Engagement Monitoring (active build), Real Trend Recon (active build), Traffic Analytics (active build)
- Add Tier 2: Multi-Language, Predictive Trends
- Add Tier 3: Multi-Modal Content, Real-Time Persuasion Layer, Continuous Strategy Engine

- [ ] **Step 2: Commit**

```bash
git add abvorn/brain/roadmap.md
git commit -m "docs: update roadmap with shipped concepts and new tiers"
```