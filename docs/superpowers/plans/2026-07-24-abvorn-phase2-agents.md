# Abvorn Phase 2 — True Agents & Knowledge Layer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Abvorn from a pipeline into a living system with knowledge-augmented agents, real-time coordination, continuous operation, and visual content generation.

**Architecture:** Three layers: (1) Knowledge Layer ingests the NotebookLM brain PDFs into a queryable store that surfaces copywriting principles, psychological triggers, and SEO tactics contextually per niche; (2) Agent Layer runs specialized async agents (Research, Content, Deploy) that communicate via a SQLite-backed event bus; (3) Daemon Layer keeps everything alive 24/7 with health monitoring, self-healing, and a CLI.

**Tech Stack:** Python 3.10+, SQLite3, sentence-transformers (or lightweight local embeddings), asyncio, PyGithub, openai, BeautifulSoup4, pdfplumber

---
## Global Constraints

- All state through SQLite (AbvornState), never direct file I/O
- No `except: pass` — every error path must log or escalate
- Knowledge layer must detect new/modified PDFs on refresh
- Every agent must have defined lifecycle: perceive → decide → act → reflect
- AgentBus topics are the single coordination mechanism — no shared state between agents
- Daemon must self-heal: restart crashed agents, log failures, alert via Telegram
- Open Design MCP wiring must be automated (one command after install)
- The brain directory path must be configurable (env var `ABVORN_BRAIN_PATH`)

---

### Task 1: Brain Ingestion Engine

**Files:**
- Create: `abvorn/brain/__init__.py`
- Create: `abvorn/brain/scanner.py`
- Create: `abvorn/brain/indexer.py`
- Create: `abvorn/brain/retriever.py`
- Test: `tests/test_brain.py`

**Interfaces:**
- Consumes: `AbvornState` from Phase 1, PDF files at `ABVORN_BRAIN_PATH`
- Produces: `KnowledgeIndex.index_brain(path) -> dict`, `KnowledgeRetriever.query(niche, angle, persona) -> list[dict]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_brain.py
import pytest
from pathlib import Path
from abvorn.brain.indexer import KnowledgeIndex
from abvorn.brain.retriever import KnowledgeRetriever

def test_index_and_retrieve():
    """Should index a test PDF and retrieve knowledge from it."""
    index = KnowledgeIndex(":memory:")
    index.ingest_text("test_domain", "Test Doc", "This is a psychological principle about buying behavior. Scarcity increases desire.")
    retriever = KnowledgeRetriever(index)
    results = retriever.query("buying behavior", top_k=5)
    assert len(results) > 0
    assert "scarcity" in results[0]["text"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_brain.py::test_index_and_retrieve -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create scanner module**

```python
# abvorn/brain/scanner.py
"""Walks the brain directory, detects new/modified PDFs, extracts text."""

import hashlib, logging, json, os, re
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("abvorn.brain.scanner")

BRAIN_PATH = Path(os.environ.get("ABVORN_BRAIN_PATH", ""))
DEFAULT_PATHS = [
    BRAIN_PATH,
    Path("/content/drive/MyDrive/Notebook LM Brain"),
    Path.home() / ".abvorn" / "brain",
]

def _find_brain() -> Path:
    for p in DEFAULT_PATHS:
        if p.exists():
            return p
    local = Path.home() / ".abvorn" / "brain"
    local.mkdir(parents=True, exist_ok=True)
    return local

def scan_brain() -> dict:
    """Walk the brain directory, return categorized file listing."""
    brain = _find_brain()
    if not brain.exists():
        logger.warning(f"Brain directory not found: {brain}")
        return {}
    categories = {}
    for entry in brain.iterdir():
        if entry.is_dir():
            pdfs = list(entry.glob("*.pdf")) + list(entry.glob("*.PDF"))
            if pdfs:
                cat_name = entry.name.replace("_", " ").title()
                categories[cat_name] = []
                for pdf in pdfs:
                    mtime = datetime.fromtimestamp(pdf.stat().st_mtime)
                    h = hashlib.md5(pdf.read_bytes()[:4096]).hexdigest()
                    categories[cat_name].append({
                        "path": str(pdf),
                        "name": pdf.stem,
                        "size": pdf.stat().st_size,
                        "modified": mtime.isoformat(),
                        "hash": h,
                    })
    total = sum(len(v) for v in categories.values())
    logger.info(f"Brain scan: {len(categories)} categories, {total} documents")
    return categories

def extract_text(pdf_path: str) -> str:
    """Extract text from a PDF file using pdfplumber."""
    import pdfplumber
    text_parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
    except Exception as e:
        logger.warning(f"PDF extract failed for {pdf_path}: {e}")
        return ""
    full = "\n".join(text_parts)
    return full[:50000]
```

- [ ] **Step 4: Create indexer module**

```python
# abvorn/brain/indexer.py
"""Indexes extracted text into a queryable SQLite store with keyword + semantic search."""

import json, logging, hashlib, re, sqlite3, threading
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger("abvorn.brain.indexer")

STOPWORDS = {"the","a","an","is","are","was","were","be","been","being",
             "have","has","had","do","does","did","will","would","shall",
             "should","may","might","must","can","could","i","you","he",
             "she","it","we","they","this","that","these","those","and",
             "or","but","not","nor","for","with","on","at","in","of",
             "to","by","from","as","into","through","during","before",
             "after","above","below","between","out","off","over","under"}

class KnowledgeIndex:
    """SQLite-indexed knowledge base with keyword and embedding search."""

    def __init__(self, db_path):
        self._db_path = db_path
        self._local = threading.local()
        self._init_db()

    @contextmanager
    def _cursor(self):
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path))
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        yield self._local.conn.cursor()
        self._local.conn.commit()

    def _init_db(self):
        with self._cursor() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL,
                    title TEXT NOT NULL,
                    path TEXT,
                    hash TEXT,
                    indexed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER NOT NULL REFERENCES documents(id),
                    chunk_index INT NOT NULL,
                    text TEXT NOT NULL,
                    tokens TEXT
                );
                CREATE TABLE IF NOT EXISTS domain_tags (
                    domain TEXT PRIMARY KEY,
                    keywords TEXT NOT NULL,
                    summary TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_tokens ON chunks(tokens);
            """)

    def _tokenize(self, text: str) -> str:
        tokens = re.findall(r'\b[a-z]{3,}\b', text.lower())
        return " ".join(t for t in tokens if t not in STOPWORDS)

    def _chunk_text(self, text: str, max_chars: int = 1500) -> list[str]:
        paragraphs = text.split("\n\n")
        chunks = []
        current = ""
        for p in paragraphs:
            stripped = p.strip()
            if not stripped:
                continue
            if len(current) + len(stripped) < max_chars:
                current += "\n\n" + stripped if current else stripped
            else:
                if current:
                    chunks.append(current)
                current = stripped
        if current:
            chunks.append(current)
        return chunks if chunks else [text[:max_chars]]

    def ingest_text(self, domain: str, title: str, text: str, path: str = "", file_hash: str = "") -> int:
        chunks = self._chunk_text(text)
        doc_hash = hashlib.md5(text[:8192].encode()).hexdigest()
        with self._cursor() as c:
            c.execute("INSERT INTO documents (domain, title, path, hash, indexed_at) VALUES (?, ?, ?, ?, ?)",
                      (domain, title, path, doc_hash, datetime.now().isoformat()))
            doc_id = c.lastrowid
            for i, chunk in enumerate(chunks):
                tokens = self._tokenize(chunk)
                c.execute("INSERT INTO chunks (doc_id, chunk_index, text, tokens) VALUES (?, ?, ?, ?)",
                          (doc_id, i, chunk, tokens))
            # Derive domain keywords from all chunks
            all_tokens = self._tokenize(text)
            c.execute("INSERT OR REPLACE INTO domain_tags (domain, keywords) VALUES (?, ?)",
                      (domain, all_tokens[:500]))
        logger.info(f"Indexed '{title}': {len(chunks)} chunks in domain '{domain}'")
        return doc_id

    def ingest_pdf(self, pdf_path: str, domain: str, text: str, file_hash: str = "") -> int:
        title = Path(pdf_path).stem
        return self.ingest_text(domain, title, text, pdf_path, file_hash)

    def get_domain_keywords(self, domain: str) -> str:
        with self._cursor() as c:
            c.execute("SELECT keywords FROM domain_tags WHERE domain=?", (domain,))
            row = c.fetchone()
            return row[0] if row else ""

    def get_document_count(self) -> int:
        with self._cursor() as c:
            c.execute("SELECT COUNT(*) FROM documents")
            return c.fetchone()[0]

    def get_chunk_count(self) -> int:
        with self._cursor() as c:
            c.execute("SELECT COUNT(*) FROM chunks")
            return c.fetchone()[0]
```

- [ ] **Step 5: Create retriever module**

```python
# abvorn/brain/retriever.py
"""Queries the knowledge index using keyword matching and returns relevant chunks."""

import json, logging, re, sqlite3

logger = logging.getLogger("abvorn.brain.retriever")

STOPWORDS = {"the","a","an","is","are","was","were","be","been","being",
             "have","has","had","do","does","did","will","would","shall",
             "should","may","might","must","can","could","i","you","he",
             "she","it","we","they","this","that","these","those","and",
             "or","but","not","nor","for","with","on","at","in","of",
             "to","by","from","as","into","through","during","before",
             "after","above","below","between","out","off","over","under"}

class KnowledgeRetriever:
    """Retrieves knowledge chunks relevant to a query using keyword scoring."""

    def __init__(self, index):
        self._index = index
        self._domain_cache = {}

    def _tokenize(self, text: str) -> set:
        return set(re.findall(r'\b[a-z]{3,}\b', text.lower())) - STOPWORDS

    def query(self, query_text: str, top_k: int = 10, domain_filter: str = None) -> list[dict]:
        query_tokens = self._tokenize(query_text)
        if not query_tokens:
            return []

        with self._index._cursor() as c:
            if domain_filter:
                c.execute("""
                    SELECT c.id, c.text, c.tokens, d.domain, d.title
                    FROM chunks c JOIN documents d ON c.doc_id = d.id
                    WHERE d.domain = ?
                """, (domain_filter,))
            else:
                c.execute("""
                    SELECT c.id, c.text, c.tokens, d.domain, d.title
                    FROM chunks c JOIN documents d ON c.doc_id = d.id
                """)

            scored = []
            for row in c.fetchall():
                chunk_id, text, tokens_field, domain, title = row
                if not tokens_field:
                    continue
                chunk_tokens = set(tokens_field.split())
                overlap = len(query_tokens & chunk_tokens)
                if overlap > 0:
                    scored.append((overlap / len(query_tokens), {
                        "id": chunk_id,
                        "text": text[:2000],
                        "domain": domain,
                        "title": title,
                        "relevance": round(overlap / len(query_tokens), 2),
                    }))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:top_k]]

    def query_for_pipeline(self, niche: str, angle: str = "", persona: dict = None) -> dict:
        """Build a context bundle for the content pipeline."""
        query_parts = [niche, angle]
        if persona:
            query_parts.extend(persona.get("frustrations", []))
            query_parts.extend(persona.get("desires", []))
        query = " ".join(query_parts)

        chunks = self.query(query, top_k=8)
        results = {"chunks": chunks, "total": len(chunks)}

        if chunks:
            results["copywriting_principles"] = [
                c for c in chunks if c["domain"] in ("Copywriting",)
            ]
            results["psychology_triggers"] = [
                c for c in chunks if c["domain"] in ("Consumer_Psychology_and_Buyer_Behavior",)
            ]
            results["seo_tactics"] = [
                c for c in chunks if c["domain"] in ("SEO", "Conversion_Rate_Optimisation",)
            ]

        return results

    def summarize_knowledge_base(self) -> dict:
        """Return a summary of what's in the brain."""
        with self._index._cursor() as c:
            c.execute("""
                SELECT d.domain, COUNT(*) as doc_count, COUNT(c.id) as chunk_count
                FROM documents d LEFT JOIN chunks c ON c.doc_id = d.id
                GROUP BY d.domain ORDER BY doc_count DESC
            """)
            domains = []
            for row in c.fetchall():
                domains.append({"domain": row[0], "documents": row[1], "chunks": row[2]})
            c.execute("SELECT SUM(c) FROM (SELECT COUNT(*) as c FROM documents UNION ALL SELECT COUNT(*) FROM chunks)")
            total_docs = sum(r["documents"] for r in domains)
            total_chunks = sum(r["chunks"] for r in domains)
            return {"domains": domains, "total_documents": total_docs, "total_chunks": total_chunks}
```

- [ ] **Step 6: Create `abvorn/brain/__init__.py`**

```python
# abvorn/brain/__init__.py
from .scanner import scan_brain, extract_text, _find_brain
from .indexer import KnowledgeIndex
from .retriever import KnowledgeRetriever
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_brain.py::test_index_and_retrieve -v`
Expected: PASS

- [ ] **Step 8: Create the full brain refresh orchestrator**

```python
# Add to abvorn/brain/__init__.py or create abvorn/brain/orchestrator.py
import json, logging
from pathlib import Path
from .scanner import scan_brain, extract_text
from .indexer import KnowledgeIndex
from .retriever import KnowledgeRetriever

logger = logging.getLogger("abvorn.brain")

BRAIN_DB_PATH = Path.home() / ".abvorn" / "brain_index.db"

def refresh_brain() -> dict:
    """Full brain refresh: scan → extract → index → return summary."""
    categories = scan_brain()
    if not categories:
        return {"status": "no_brain", "documents": 0}

    index = KnowledgeIndex(str(BRAIN_DB_PATH))
    indexed = 0

    for domain, files in categories.items():
        for f in files:
            text = extract_text(f["path"])
            if text:
                index.ingest_pdf(f["path"], domain, text, f.get("hash", ""))
                indexed += 1

    retriever = KnowledgeRetriever(index)
    summary = retriever.summarize_knowledge_base()
    logger.info(f"Brain refresh complete: {indexed} documents indexed")
    return {"status": "ok", "indexed": indexed, "summary": summary}

def get_brain_retriever() -> KnowledgeRetriever:
    """Get or create a retriever for the current brain index."""
    if not BRAIN_DB_PATH.exists():
        refresh_brain()
    index = KnowledgeIndex(str(BRAIN_DB_PATH))
    return KnowledgeRetriever(index)
```

- [ ] **Step 9: Commit**

```bash
git add abvorn/brain/ tests/test_brain.py
git commit -m "feat: add brain ingestion engine with PDF scanning, indexing, and knowledge retrieval"
```

---

### Task 2: Knowledge-Augmented Content Pipeline

**Files:**
- Modify: `abvorn/content/pipeline.py` (inject brain context into stages)
- Modify: `abvorn/agents/writer.py` (generate_outline and write_draft use brain context)
- Modify: `abvorn/agents/editor.py` (fact_check and polish use brain principles)
- Test: `tests/test_brain_pipeline.py`

**Interfaces:**
- Consumes: `KnowledgeRetriever` from Task 1, existing pipeline from Phase 1
- Produces: knowledge-augmented content with copywriting principles, psychology triggers, and SEO tactics injected

- [ ] **Step 1: Write the failing test**

```python
# tests/test_brain_pipeline.py
import pytest
from abvorn.brain.indexer import KnowledgeIndex
from abvorn.brain.retriever import KnowledgeRetriever
from abvorn.content.pipeline import ContentPipeline

def test_knowledge_augmented_pipeline():
    """Pipeline with brain context should include knowledge signals."""
    index = KnowledgeIndex(":memory:")
    index.ingest_text("Copywriting", "Breakthrough Advertising",
        "The most powerful advertising principle is the problem-awareness level. "
        "Match the intensity of the prospect's awareness of their problem.")
    retriever = KnowledgeRetriever(index)

    class FakeRouter:
        def ask(self, prompt, **kw):
            return json.dumps({
                "outline": ["H2: Introduction", "H2: Product Review"],
                "post_title": "Test Title",
                "meta_description": "Test meta description for SEO here it is long enough",
                "intro": "<p>Test intro</p>",
                "article_html": "<p>Test article</p>",
                "faqs": [{"question": "Q1?", "answer": "A1."}],
                "tags": ["test"],
                "socials": {"x": "tweet", "linkedin": "post"}
            })

    pipeline = ContentPipeline()
    pipeline.brain = retriever
    result = pipeline.run("test_niche", FakeRouter(), persona={})
    assert result is not None
    assert "post_title" in result
```

- [ ] **Step 2: Modify pipeline to inject brain context**

In `abvorn/content/pipeline.py`, add a `brain` attribute and modify `run()` to pass brain context to each stage:

```python
# Add to ContentPipeline.__init__
self.brain = None

# In run(), after Stage 1 (RESEARCH) and before Stage 2 (OUTLINE):
brain_context = {}
if self.brain:
    brain_context = self.brain.query_for_pipeline(niche, outline.get("selected_angle", ""), persona)

# Pass brain_context to generate_outline and write_draft:
# Stage 2: OUTLINE
outline = generate_outline(niche, products, persona or {}, router, brain_context.get("chunks", []))

# Stage 3: DRAFT
draft = write_draft(niche, products, outline, persona or {}, products, router, brain_context)

# Stage 4: FACT-CHECK - use psychology principles for deeper analysis
# Stage 5: POLISH - use copywriting principles for conversion optimization
```

- [ ] **Step 3: Update generate_outline to accept brain chunks**

Modify `generate_outline()` to accept a `knowledge_chunks` parameter. Inject the most relevant chunk into the prompt as "expert guidance":

```python
def generate_outline(niche: str, products: list, persona: dict, router, knowledge_chunks: list = None) -> dict:
    # ...existing code...
    expert_guidance = ""
    if knowledge_chunks:
        top = knowledge_chunks[0]["text"][:500] if knowledge_chunks else ""
        if top:
            expert_guidance = f"\n\nEXPERT GUIDANCE:\n{top}\n\nApply this principle when selecting your angle and outline."

    prompt = f"""You are a content strategist planning a buying guide for '{niche}'.
Products: {json.dumps(product_names)}
{persona_context}
{expert_guidance}
# ...rest of existing prompt...
"""
```

- [ ] **Step 4: Update write_draft to accept brain context**

```python
def write_draft(niche: str, products: list, outline: dict, persona: dict,
                research_data: list, router, brain_context: dict = None) -> dict:
    # ...existing code...
    copywriting_guidance = ""
    psych_guidance = ""
    seo_guidance = ""
    if brain_context:
        copy_principles = brain_context.get("copywriting_principles", [])
        if copy_principles:
            texts = [c["text"][:300] for c in copy_principles[:2]]
            copywriting_guidance = "\nCOPYWRITING PRINCIPLES:\n" + "\n---\n".join(texts)
        psych_triggers = brain_context.get("psychology_triggers", [])
        if psych_triggers:
            texts = [c["text"][:300] for c in psych_triggers[:2]]
            psych_guidance = "\nPSYCHOLOGY TRIGGERS:\n" + "\n---\n".join(texts)
        seo_tactics = brain_context.get("seo_tactics", [])
        if seo_tactics:
            texts = [c["text"][:300] for c in seo_tactics[:2]]
            seo_guidance = "\nSEO TACTICS:\n" + "\n---\n".join(texts)

    prompt = f"""Write a comprehensive buying guide for '{niche}'.

PRODUCTS TO FEATURE:
{product_json}
{copywriting_guidance}
{psych_guidance}
{seo_guidance}
# ...rest of existing prompt...
"""
```

- [ ] **Step 5: Update editor stages to accept brain context**

Modify `fact_check()` and `polish()` to accept an optional `brain_context` parameter. Inject copywriting and psychology principles into their prompts for deeper analysis.

- [ ] **Step 6: Run test**

Run: `pytest tests/test_brain_pipeline.py -v`
Expected: PASS

- [ ] **Step 7: Verify all existing tests still pass**

Run: `pytest tests/ -v`
Expected: 4/4 passing

- [ ] **Step 8: Commit**

```bash
git add abvorn/content/pipeline.py abvorn/agents/writer.py abvorn/agents/editor.py tests/test_brain_pipeline.py
git commit -m "feat: knowledge-augmented pipeline with copywriting, psychology, and SEO guidance from brain"
```

---

### Task 3: AgentBus — Event-Driven Coordination

**Files:**
- Create: `abvorn/core/bus.py`
- Test: `tests/test_bus.py`

**Interfaces:**
- Consumes: `AbvornState` from Phase 1
- Produces: `AgentBus.publish(topic, message)`, `AgentBus.subscribe(topic, callback)`, `AgentBus.run_forever()`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bus.py
import pytest, time, threading
from abvorn.core.bus import AgentBus

def test_publish_subscribe():
    bus = AgentBus(":memory:")
    received = []
    def handler(msg):
        received.append(msg)
    bus.subscribe("test.topic", handler)
    bus.publish("test.topic", {"data": "hello"})
    time.sleep(0.1)
    assert len(received) == 1
    assert received[0]["data"] == "hello"

def test_topic_filtering():
    bus = AgentBus(":memory:")
    received = []
    bus.subscribe("content.drafted", received.append)
    bus.publish("content.researched", {"niche": "test"})
    time.sleep(0.1)
    assert len(received) == 0  # wrong topic
    bus.publish("content.drafted", {"niche": "test"})
    time.sleep(0.1)
    assert len(received) == 1
```

- [ ] **Step 2: Implement AgentBus**

```python
# abvorn/core/bus.py
import json, logging, threading, time, sqlite3
from datetime import datetime
from collections import defaultdict
from contextlib import contextmanager

logger = logging.getLogger("abvorn.bus")

TOPIC_PATTERNS = {
    "content.researched": "research_complete",
    "content.drafted": "draft_complete",
    "content.published": "publish_complete",
    "analytics.updated": "analytics_refresh",
    "system.error": "error_occurred",
    "system.heartbeat": "agent_alive",
    "brain.refreshed": "brain_update",
    "agent.spawned": "new_agent",
}

class AgentBus:
    """SQLite-backed event bus for inter-agent communication."""

    def __init__(self, db_path):
        self._db_path = db_path
        self._local = threading.local()
        self._subscribers = defaultdict(list)
        self._running = False
        self._lock = threading.Lock()
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
            c.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    processed INTEGER DEFAULT 0
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_events_topic ON events(topic)")

    def publish(self, topic: str, message: dict):
        """Publish an event to the bus. All subscribers to this topic receive it."""
        with self._cursor() as c:
            c.execute("INSERT INTO events (topic, message, created_at) VALUES (?, ?, ?)",
                      (topic, json.dumps(message), datetime.now().isoformat()))
        logger.debug(f"[BUS] Published: {topic}")
        with self._lock:
            for callback in self._subscribers.get(topic, []):
                try:
                    callback(message)
                except Exception as e:
                    logger.error(f"[BUS] Subscriber error on {topic}: {e}")

    def subscribe(self, topic: str, callback):
        """Register a callback for a topic. Callback receives the message dict."""
        with self._lock:
            self._subscribers[topic].append(callback)
        logger.debug(f"[BUS] Subscribed: {topic}")

    def unsubscribe(self, topic: str, callback):
        with self._lock:
            if callback in self._subscribers[topic]:
                self._subscribers[topic].remove(callback)

    def get_recent_events(self, topic: str = None, limit: int = 20) -> list:
        with self._cursor() as c:
            if topic:
                c.execute("SELECT * FROM events WHERE topic=? ORDER BY id DESC LIMIT ?", (topic, limit))
            else:
                c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
            return [{"id": r[0], "topic": r[1], "message": json.loads(r[2]), "created_at": r[3]} for r in c.fetchall()]

    def run_forever(self, poll_interval: float = 0.5):
        """Run the bus event loop (for future async agents to process persisted events)."""
        self._running = True
        last_id = 0
        while self._running:
            with self._cursor() as c:
                c.execute("SELECT * FROM events WHERE id > ? AND processed=0 ORDER BY id", (last_id,))
                for row in c.fetchall():
                    event = {"id": row[0], "topic": row[1], "message": json.loads(row[2]), "created_at": row[3]}
                    with self._lock:
                        for callback in self._subscribers.get(event["topic"], []):
                            try:
                                callback(event["message"])
                            except Exception as e:
                                logger.error(f"[BUS] Subscriber error on {event['topic']}: {e}")
                    c.execute("UPDATE events SET processed=1 WHERE id=?", (event["id"],))
                    last_id = event["id"]
            time.sleep(poll_interval)

    def stop(self):
        self._running = False
```

- [ ] **Step 3: Run tests to verify**

Run: `pytest tests/test_bus.py -v`
Expected: 2/2 PASS

- [ ] **Step 4: Commit**

```bash
git add abvorn/core/bus.py tests/test_bus.py
git commit -m "feat: add AgentBus event-driven coordination layer"
```

---

### Task 4: True Agent System

**Files:**
- Modify: `abvorn/agents/base.py` (full async agent lifecycle)
- Create: `abvorn/agents/orchestrator.py`
- Test: `tests/test_agents.py`

**Interfaces:**
- Consumes: `AgentBus` from Task 3, `KnowledgeRetriever` from Task 1, `ContentPipeline` from Phase 1
- Produces: `AgentBase` (async lifecycle), `ResearchAgent`, `ContentAgent`, `DeployAgent`, `AgentOrchestrator`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agents.py
import pytest, asyncio
from abvorn.agents.base import AgentBase
from abvorn.core.bus import AgentBus

def test_agent_lifecycle():
    """Agent should go through perceive → decide → act → reflect cycle."""
    bus = AgentBus(":memory:")
    class TestAgent(AgentBase):
        def __init__(self):
            super().__init__("test_agent", bus)
            self.cycle_count = 0
        async def perceive(self):
            return {"events": self.bus.get_recent_events("test.topic")}
        async def decide(self, perception):
            return "act_on_test" if perception["events"] else "wait"
        async def act(self, decision):
            if decision == "act_on_test":
                self.cycle_count += 1
        async def reflect(self, outcome):
            pass

    agent = TestAgent()
    bus.publish("test.topic", {"msg": "hello"})
    asyncio.run(agent.run_once())
    assert agent.cycle_count == 1
```

- [ ] **Step 2: Implement AgentBase**

```python
# abvorn/agents/base.py
import asyncio, logging, time
from abc import ABC, abstractmethod

logger = logging.getLogger("abvorn.agents")

class AgentBase(ABC):
    """Base class for all agents with async lifecycle."""

    def __init__(self, name: str, bus, state=None, brain=None):
        self.name = name
        self.bus = bus
        self.state = state
        self.brain = brain
        self.cycle_count = 0
        self._running = False
        self._last_heartbeat = 0.0

    @abstractmethod
    async def perceive(self) -> dict:
        """Sense the environment: check bus events, state, analytics."""

    @abstractmethod
    async def decide(self, perception: dict) -> str:
        """Decide what action to take based on perception."""

    @abstractmethod
    async def act(self, decision: str):
        """Execute the decided action."""

    @abstractmethod
    async def reflect(self, outcome):
        """Learn from what happened."""

    async def run_once(self) -> dict:
        """Execute one perceive→decide→act→reflect cycle."""
        self.cycle_count += 1
        try:
            perception = await self.perceive()
            decision = await self.decide(perception)
            outcome = None
            if decision and decision != "wait":
                act_start = time.time()
                outcome = await self.act(decision)
                act_time = time.time() - act_start
                logger.info(f"[{self.name}] Cycle {self.cycle_count}: {decision} ({act_time:.1f}s)")
            await self.reflect(outcome)
            self.bus.publish("system.heartbeat", {"agent": self.name, "cycle": self.cycle_count})
            return {"decision": decision, "outcome": outcome}
        except Exception as e:
            logger.error(f"[{self.name}] Cycle {self.cycle_count} failed: {e}")
            self.bus.publish("system.error", {"agent": self.name, "error": str(e)})
            return {"error": str(e)}

    async def run_forever(self, poll_interval: float = 5.0):
        """Run the agent lifecycle indefinitely."""
        self._running = True
        while self._running:
            await self.run_once()
            await asyncio.sleep(poll_interval)

    def stop(self):
        self._running = False
```

- [ ] **Step 3: Create ResearchAgent**

```python
# abvorn/agents/orchestrator.py
import asyncio, json, logging
from datetime import datetime
from .base import AgentBase
from ..brain.retriever import KnowledgeRetriever
from ..agents.researcher import research_niche
from ..core.models import ModelRouter

logger = logging.getLogger("abvorn.orchestrator")

class ResearchAgent(AgentBase):
    """Performs product research when content is needed for a niche."""

    def __init__(self, bus, state, router: ModelRouter, brain=None):
        super().__init__("ResearchAgent", bus, state, brain)
        self.router = router

    async def perceive(self):
        queue = self.state.get_all_niches() if self.state else []
        low_posts = [n for n in queue if n["total_posts"] < 3]
        return {"under_researched": low_posts[:1]}

    async def decide(self, perception):
        if perception.get("under_researched"):
            return f"research:{perception['under_researched'][0]['slug']}"
        return "wait"

    async def act(self, decision):
        if decision.startswith("research:"):
            niche = decision.split(":", 1)[1]
            logger.info(f"[ResearchAgent] Researching niche: {niche}")
            products = research_niche(niche, self.router)
            if products:
                self.bus.publish("content.researched", {"niche": niche, "products": products, "count": len(products)})
                return {"niche": niche, "products_count": len(products)}
            logger.warning(f"[ResearchAgent] No products found for {niche}")
            return {"niche": niche, "products_count": 0}

    async def reflect(self, outcome):
        if outcome and outcome.get("products_count", 0) == 0:
            logger.warning(f"[ResearchAgent] Zero products — consider switching search strategy")


class ContentAgent(AgentBase):
    """Generates content using the pipeline when research is ready."""

    def __init__(self, bus, state, router: ModelRouter, pipeline, brain=None):
        super().__init__("ContentAgent", bus, state, brain)
        self.router = router
        self.pipeline = pipeline

    async def perceive(self):
        return {"events": self.bus.get_recent_events("content.researched")}

    async def decide(self, perception):
        if perception.get("events"):
            last = max(perception["events"], key=lambda e: e["created_at"])
            return f"generate:{last['niche']}"
        return "wait"

    async def act(self, decision):
        if decision.startswith("generate:"):
            niche = decision.split(":", 1)[1]
            logger.info(f"[ContentAgent] Generating content for: {niche}")
            result = self.pipeline.run(niche, self.router, persona={})
            if result:
                self.bus.publish("content.drafted", {"niche": niche, "result": result})
                if self.state:
                    self.state.add_post(niche, result.get("post_title", ""), "",
                                        quality_score=result.get("quality_score", 0))
                return {"niche": niche, "title": result.get("post_title", "")}
            return {"niche": niche, "error": "pipeline returned None"}

    async def reflect(self, outcome):
        if outcome and outcome.get("error"):
            logger.warning(f"[ContentAgent] Content generation failed: {outcome['error']}")


class DeployAgent(AgentBase):
    """Deploys drafted content to GitHub Pages."""

    def __init__(self, bus, state, deployer):
        super().__init__("DeployAgent", bus, state)
        self.deployer = deployer

    async def perceive(self):
        return {"events": self.bus.get_recent_events("content.drafted")}

    async def decide(self, perception):
        if perception.get("events"):
            last = max(perception["events"], key=lambda e: e["created_at"])
            return f"deploy:{last['niche']}"
        return "wait"

    async def act(self, decision):
        if decision.startswith("deploy:"):
            niche = decision.split(":", 1)[1]
            logger.info(f"[DeployAgent] Deploying content for: {niche}")
            # TODO: call deployer.deploy(niche) in Phase 2b
            self.bus.publish("content.published", {"niche": niche, "status": "deployed"})
            return {"niche": niche, "status": "deployed"}

    async def reflect(self, outcome):
        pass
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_agents.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add abvorn/agents/base.py abvorn/agents/orchestrator.py tests/test_agents.py
git commit -m "feat: add true agent system with async lifecycle (ResearchAgent, ContentAgent, DeployAgent)"
```

---

### Task 5: GitHub Pages Deploy Agent

**Files:**
- Modify: `abvorn/deploy/github.py` (full deploy implementation)
- Test: `tests/test_deploy.py`

**Interfaces:**
- Consumes: `ContentPipeline` output, `AbvornState`
- Produces: `GitHubDeployer.deploy(content, niche) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_deploy.py
import pytest, tempfile, json
from pathlib import Path
from abvorn.deploy.github import GitHubDeployer

def test_prepare_deploy():
    """Should prepare files for deployment without pushing."""
    deployer = GitHubDeployer(token="fake", repo="user/repo")
    content = {
        "post_title": "Test Post",
        "article_html": "<p>Test</p>",
        "niche_slug": "test-niche",
        "products": [{"name": "Product A"}],
        "tags": ["test"],
    }
    with tempfile.TemporaryDirectory() as tmp:
        files = deployer.prepare_files(content, Path(tmp))
        assert len(files) > 0
        for f in files:
            assert Path(f).exists()
```

- [ ] **Step 2: Implement GitHubDeployer**

```python
# abvorn/deploy/github.py
import os, json, logging, base64, re, html
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

logger = logging.getLogger("abvorn.deploy")

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{tags}">
{seo_tags}
<link rel="stylesheet" href="/assets/style.css">
</head>
<body>
<article>
<h1>{title}</h1>
{content}
</article>
<script type="application/ld+json">{schema}</script>
</body>
</html>"""

class GitHubDeployer:
    """Deploys content to GitHub Pages via the GitHub API."""

    def __init__(self, token: str, repo: str, branch: str = "main", site_dir: str = ""):
        self.token = token
        self.repo = repo
        self.branch = branch
        self.site_dir = Path(site_dir) if site_dir else Path("docs")

    def prepare_files(self, content: dict, output_dir: Path) -> list[str]:
        """Generate HTML files for a content item."""
        slug = content.get("niche_slug", content.get("post_title", "post").lower().replace(" ", "-"))
        safe_slug = re.sub(r'[^a-z0-9-]', '', slug.lower())[:80]

        article_html = content.get("article_html", "")
        intro = content.get("intro", "")
        meta_desc = content.get("meta_description", "")[:160]
        title = html.escape(content.get("post_title", "Post"), quote=True)
        tags_str = ", ".join(content.get("tags", []))
        schema_json = json.dumps(content.get("schema", {}))

        seo_tags = f'<link rel="canonical" href="https://{self.repo.split("/")[0]}.github.io/{self.repo.split("/")[1]}/{safe_slug}/">'

        full_html = TEMPLATE.format(
            title=title, meta_desc=meta_desc, tags=tags_str,
            seo_tags=seo_tags, content=intro + "\n" + article_html,
            schema=schema_json,
        )

        post_dir = output_dir / safe_slug
        post_dir.mkdir(parents=True, exist_ok=True)
        index_file = post_dir / "index.html"
        index_file.write_text(full_html, encoding="utf-8")
        logger.info(f"Prepared: {index_file}")
        return [str(index_file)]

    def deploy(self, niche_slug: str) -> dict:
        """Push generated files to GitHub using PyGithub."""
        from github import Github
        from github import InputGitTreeElement

        try:
            g = Github(self.token)
            repo = g.get_repo(self.repo)
            site_path = self.site_dir / niche_slug / "index.html"

            if not site_path.exists():
                return {"status": "error", "message": f"File not found: {site_path}"}

            with open(site_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Get or create the branch reference
            try:
                ref = repo.get_git_ref(f"heads/{self.branch}")
                base_sha = ref.object.sha
                base_tree = repo.get_git_tree(base_sha)
            except Exception:
                # Branch doesn't exist, use default
                ref = repo.get_git_ref("heads/main")
                base_sha = ref.object.sha
                base_tree = repo.get_git_tree(base_sha)

            # Create blob and tree
            blob = repo.create_git_blob(content, "utf-8")
            relative_path = str(self.site_dir.name / niche_slug / "index.html")
            element = InputGitTreeElement(relative_path, "100644", "blob", sha=blob.sha)
            new_tree = repo.create_git_tree([element], base_tree)

            # Create commit and update ref
            parent = repo.get_git_commit(base_sha)
            commit = repo.create_git_commit(f"feat: deploy {niche_slug}", new_tree, [parent])
            ref.edit(commit.sha)

            deploy_url = f"https://{self.repo.split('/')[0]}.github.io/{self.repo.split('/')[1]}/{niche_slug}/"
            logger.info(f"Deployed: {deploy_url}")
            return {"status": "success", "url": deploy_url, "commit": commit.sha}

        except Exception as e:
            logger.error(f"Deploy failed for {niche_slug}: {e}")
            return {"status": "error", "message": str(e)}
```

- [ ] **Step 3: Run test**

Run: `pytest tests/test_deploy.py::test_prepare_deploy -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add abvorn/deploy/github.py tests/test_deploy.py
git commit -m "feat: add GitHub Pages deploy agent with HTML templating and API push"
```

---

### Task 6: Daemon Mode — Continuous Operation

**Files:**
- Create: `abvorn/__main__.py`
- Create: `abvorn/daemon.py`
- Modify: `abvorn_cycle.py` (integrate daemon mode)
- Test: `tests/test_daemon.py`

**Interfaces:**
- Consumes: all agents from Task 4, brain from Task 1
- Produces: `python -m abvorn daemon` entry point, `python -m abvorn brain-refresh` CLI

- [ ] **Step 1: Write the failing test**

```python
# tests/test_daemon.py
import pytest, asyncio
from abvorn.daemon import AbvornDaemon

def test_daemon_start_stop():
    """Daemon should start agents, run briefly, and stop cleanly."""
    async def test():
        daemon = AbvornDaemon(":memory:")
        await daemon.start()
        await asyncio.sleep(0.5)
        await daemon.stop()
        assert daemon.running == False
    asyncio.run(test())
```

- [ ] **Step 2: Create daemon module**

```python
# abvorn/daemon.py
"""Abvorn daemon — runs all agents continuously."""

import asyncio, logging, signal, sys, json
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("abvorn.daemon")

from .core.state import AbvornState
from .core.models import ModelRouter
from .core.secrets import load_secrets
from .core.bus import AgentBus
from .content.pipeline import ContentPipeline
from .agents.orchestrator import ResearchAgent, ContentAgent, DeployAgent
from .brain.orchestrator import refresh_brain, get_brain_retriever
from .deploy.github import GitHubDeployer

STATE_DB = Path.home() / ".abvorn" / "state.db"
BUS_DB = Path.home() / ".abvorn" / "bus.db"

class AbvornDaemon:
    """The daemon that keeps Abvorn alive 24/7."""

    def __init__(self, state_db: str = None):
        self.running = False
        self.state_path = Path(state_db) if state_db else STATE_DB
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = AbvornState(self.state_path)
        self.bus = AgentBus(str(BUS_DB))
        self.secrets = load_secrets()
        self.router = ModelRouter(self.secrets)
        self.agents = []
        self._tasks = []

    async def start(self):
        """Start all agents and the brain."""
        self.running = True
        logger.info("Abvorn daemon starting...")

        # Initialize brain
        brain = None
        try:
            result = refresh_brain()
            if result.get("status") == "ok":
                brain = get_brain_retriever()
                logger.info(f"Brain loaded: {result.get('indexed', 0)} documents")
        except Exception as e:
            logger.warning(f"Brain init failed (non-fatal): {e}")

        # Wire pipeline with brain
        pipeline = ContentPipeline(self.state)
        if brain:
            pipeline.brain = brain

        # Wire deployer
        deployer = GitHubDeployer(
            token=self.secrets.get("GITHUB_TOKEN", ""),
            repo=self.secrets.get("GITHUB_REPO", ""),
        )

        # Create agents
        self.agents = [
            ResearchAgent(self.bus, self.state, self.router, brain),
            ContentAgent(self.bus, self.state, self.router, pipeline, brain),
            DeployAgent(self.bus, self.state, deployer),
        ]

        # Subscribe agents to bus
        for agent in self.agents:
            logger.info(f"  Starting agent: {agent.name}")

        # Start agent loops
        for agent in self.agents:
            task = asyncio.create_task(agent.run_forever())
            self._tasks.append(task)

        # Start bus event loop
        bus_task = asyncio.create_task(self._bus_loop())
        self._tasks.append(bus_task)

        logger.info(f"Daemon running with {len(self.agents)} agents")

    async def _bus_loop(self):
        """Background task that processes bus events."""
        while self.running:
            events = self.bus.get_recent_events()
            await asyncio.sleep(10)

    async def stop(self):
        """Graceful shutdown of all agents."""
        logger.info("Daemon stopping...")
        self.running = False
        for agent in self.agents:
            agent.stop()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Daemon stopped")
```

- [ ] **Step 3: Create `__main__.py` entry point**

```python
# abvorn/__main__.py
"""CLI entry point: python -m abvorn <command>"""

import asyncio, logging, sys
from .daemon import AbvornDaemon
from .brain.orchestrator import refresh_brain

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    logger = logging.getLogger("abvorn")

    if len(sys.argv) < 2:
        print("Usage: python -m abvorn <command>")
        print("Commands:")
        print("  daemon        Run all agents continuously")
        print("  brain-refresh  Scan and index the knowledge brain")
        print("  once          Run one cycle of the pipeline")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "daemon":
        async def run():
            d = AbvornDaemon()
            await d.start()
            # Keep running until Ctrl+C
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                await d.stop()
        asyncio.run(run())

    elif cmd == "brain-refresh":
        result = refresh_brain()
        summary = result.get("summary", {})
        domains = summary.get("domains", [])
        print(f"Brain refresh complete: {summary.get('total_documents', 0)} documents, {summary.get('total_chunks', 0)} chunks")
        for d in domains:
            print(f"  {d['domain']}: {d['documents']} documents, {d['chunks']} chunks")

    elif cmd == "once":
        from .core.secrets import load_secrets
        from .core.models import ModelRouter
        from .content.pipeline import ContentPipeline
        secrets = load_secrets()
        router = ModelRouter(secrets)
        pipeline = ContentPipeline()
        niche = sys.argv[2] if len(sys.argv) > 2 else "wireless headphones"
        result = pipeline.run(niche, router)
        if result:
            print(f"Generated: {result.get('post_title')}")
            print(f"Quality: {result.get('quality_score')}")
        else:
            print("Pipeline failed")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test**

Run: `pytest tests/test_daemon.py::test_daemon_start_stop -v`
Expected: PASS

- [ ] **Step 5: Verify CLI entry point**

Run: `python -m abvorn brain-refresh`
Expected: "Brain refresh complete: N documents, N chunks"

- [ ] **Step 6: Commit**

```bash
git add abvorn/__main__.py abvorn/daemon.py tests/test_daemon.py
git commit -m "feat: add daemon mode with CLI entry point and continuous agent operation"
```

---

### Task 7: Open Design Integration

**Files:**
- Create: `.opencode/mcp.json` (if Open Design od CLI available, add MCP config)
- Create: `abvorn/deploy/visual.py` (bridge between Abvorn content and Open Design)
- Info: `OPEN_DESIGN_SETUP.md` (optional install guide)

**Interfaces:**
- Consumes: Open Design `od` CLI, Abvorn content artifacts
- Produces: visual content (featured images, social graphics) for each post

- [ ] **Step 1: Clone and build Open Design** (on a machine with proper Node.js setup)

Instructions saved from earlier:
```bash
git clone --depth 1 https://github.com/nexu-io/open-design.git
cd open-design
corepack enable && pnpm install
pnpm tools-dev run web
```

Then:
```bash
od mcp install opencode  # Wires Open Design into OpenCode's MCP config
```

- [ ] **Step 2: Create visual bridge module** (for when Open Design is available)

```python
# abvorn/deploy/visual.py
"""Bridge between Abvorn content pipeline and Open Design for visual generation."""

import json, logging, subprocess, os
from pathlib import Path

logger = logging.getLogger("abvorn.visual")

def generate_featured_image(post_title: str, niche: str, output_dir: Path) -> str:
    """Use Open Design to generate a featured image for a blog post."""
    output_file = output_dir / "featured.html"
    try:
        subprocess.run([
            "od", "design", "featured-image",
            "--title", post_title,
            "--niche", niche,
            "--output", str(output_file),
        ], check=True, capture_output=True, timeout=60)
        logger.info(f"Featured image generated: {output_file}")
        return str(output_file)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning(f"Open Design not available for featured image: {e}")
        return ""

def generate_social_card(post_title: str, niche: str, output_dir: Path, platform: str = "x") -> str:
    """Generate a social media card for the post."""
    output_file = output_dir / f"social-{platform}.html"
    try:
        subprocess.run([
            "od", "design", "social-card",
            "--title", post_title,
            "--niche", niche,
            "--platform", platform,
            "--output", str(output_file),
        ], check=True, capture_output=True, timeout=60)
        logger.info(f"Social card generated for {platform}: {output_file}")
        return str(output_file)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning(f"Open Design not available for social card: {e}")
        return ""
```

- [ ] **Step 3: Commit**

```bash
git add abvorn/deploy/visual.py
git commit -m "feat: add Open Design visual bridge for featured images and social cards"
```

---

### Task 8: Full Integration & Verification

**Files:**
- Modify: `abvorn/secrets.py` — add `ABVORN_BRAIN_PATH` to env_map
- Test: full integration test

- [ ] **Step 1: Add brain path to secrets**

```python
# In abvorn/core/secrets.py env_map, add:
"ABVORN_BRAIN_PATH": "ABVORN_BRAIN_PATH",
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests passing (7+ tests)

- [ ] **Step 3: Verify brain-refresh works**

Run: `python -m abvorn brain-refresh`
Expected: Scans brain directory, indexes PDFs, prints summary

- [ ] **Step 4: Verify one-shot content generation**

Run: `python -m abvorn once "wireless headphones"`
Expected: Generates content with knowledge-augmented prompts

- [ ] **Step 5: Commit**

```bash
git add abvorn/core/secrets.py
git commit -m "chore: add brain path to secrets, final integration wiring"
```