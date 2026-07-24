### CELL 1
# -*- coding: utf-8 -*-
"""Abvorn v13 — Cell 1: Living Kernel (Brain, Soul, Enterprise Architecture)"""
!pip -q install pypdf chromadb openai duckduckgo-search pytrends requests beautifulsoup4 PyGithub google-auth google-api-python-client gspread Pillow textstat jinja2

import os, pathlib, json, re, time, smtplib, shutil, sys, textstat, threading, zipfile, logging, atexit, random
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict
from html import escape as html_escape
from urllib.parse import quote_plus
import requests, gspread
from google.colab import drive, auth, userdata
from google.auth import default
from openai import OpenAI
from duckduckgo_search import DDGS
from pytrends.request import TrendReq
from bs4 import BeautifulSoup
import chromadb
from chromadb.utils import embedding_functions
from pypdf import PdfReader

from abvorn.core.secrets import load_secrets, get_boardroom_path, get_empire_path
from abvorn.core.state import AbvornState
from abvorn.core.models import ModelRouter
from abvorn.agents.editor import build_schema

drive.mount('/content/drive')

BOARDROOM_DIR = pathlib.Path('/content/drive/MyDrive/The_Synthetic_Boardroom')
EMPIRE_DIR = BOARDROOM_DIR / "6_Empire_Network"
SKILLS_DIR = BOARDROOM_DIR / "Design_Skills"
STATE_FILE = BOARDROOM_DIR / "empire_state.json"
SECRETS_FILE = BOARDROOM_DIR / "secrets.json"
GA4_CREDS_FILE = BOARDROOM_DIR / "ga4_credentials.json"
PROCESSED_BOOKS_FILE = BOARDROOM_DIR / "processed_books.json"
KILL_SWITCH_FILE = BOARDROOM_DIR / "kill_switch.flag"
HEARTBEAT_FILE = BOARDROOM_DIR / "heartbeat.json"
CHROMA_BACKUP_FILE = BOARDROOM_DIR / "chroma_backup.zip"

for d in [BOARDROOM_DIR, EMPIRE_DIR, SKILLS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', handlers=[logging.StreamHandler()])
logger = logging.getLogger("abvorn")

# ── SECRETS ─────────────────────────────────────────────────────────────────
S = load_secrets()
# Supplement with Colab userdata (takes priority over file/env)
try:
    for key in list(S.keys()):
        try:
            val = userdata.get(key)
            if val and "YOUR_" not in val: S[key] = val
        except: pass
except: pass
# Load GA4 credentials from separate file if present
if GA4_CREDS_FILE.exists():
    S["GA4_CREDENTIALS_JSON"] = GA4_CREDS_FILE.read_text().strip()

# ── SITE PATHS ──────────────────────────────────────────────────────────────
SITE_URL = S["SITE_URL"]
LOGO_URL = f"{SITE_URL}/logo.png"
GA4_MEASUREMENT_ID = S["GA4_MEASUREMENT_ID"]
GA4_API_SECRET = S["GA4_API_SECRET"]
GMAIL_USER = S["GMAIL_USER"]
GMAIL_APP_PASSWORD = S["GMAIL_APP_PASSWORD"]
TELEGRAM_TOKEN = S["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = S["TELEGRAM_CHAT_ID"]

def _compute_site_base_path(repo_full_name):
    if not repo_full_name or "/" not in repo_full_name: return ""
    owner, name = repo_full_name.split("/", 1)
    if name.lower() == f"{owner.lower()}.github.io": return ""
    return f"/{name}"

SITE_BASE_PATH = _compute_site_base_path(S["GITHUB_REPO"])

def apply_base_path(html):
    if not SITE_BASE_PATH: return html
    html = re.sub(r'(href|src)="/(?!/)', f'\\1="{SITE_BASE_PATH}/', html)
    html = re.sub(r"fetch\('/(?!/)", f"fetch('{SITE_BASE_PATH}/", html)
    return html

# ── KILL SWITCH / SAFE MODE ───────────────────────────────────────────────
if KILL_SWITCH_FILE.exists():
    print("KILL SWITCH ACTIVATED. System halted.")
    sys.exit(0)

SAFE_MODE = False
if HEARTBEAT_FILE.exists():
    try: hb = json.loads(HEARTBEAT_FILE.read_text())
    except: hb = {'last_heartbeat': '2000-01-01'}
    last = datetime.fromisoformat(hb.get('last_heartbeat', '2000-01-01'))
    if (datetime.now() - last) > timedelta(days=7):
        print("No heartbeat in 7 days. SAFE MODE (no emails).")
        SAFE_MODE = True

# ── SOUL ────────────────────────────────────────────────────────────────────
SOUL = """You are the Abvorn Empire AI – the central architect of the most advanced autonomous media
enterprise ever conceived. You are a self‑evolving, self‑designing, multi‑agent intelligence.

### OUR MISSION
Empower millions to make smarter buying decisions through hyper‑relevant, deeply researched content.

### OUR VISION
Become the invisible intelligence layer behind every profitable independent media business on Earth.

### CORE VALUES
1. Radical Customer‑Centricity – genuinely help, never mislead.
2. Data Tyranny – every decision backed by measurable performance.
3. Relentless Optimization – never stop improving.
4. Creative Brilliance – world‑class design and storytelling.
5. Autonomous Evolution – learn, patch, upgrade itself.
6. Long‑Term Greed – build sustainable assets, not quick flips.

### MASTERY PILLARS
1. Persuasion Architecture – every sentence intentional. Guide, never manipulate.
2. Autonomous Self‑Improvement – analyse failures, rewrite rules, compound growth.
3. Operational Excellence – speed, reliability, precision. Machine quality at machine speed.

### THE GENERAL SYSTEM
You are Commander in Chief. Responsibilities:
1. Enterprise Design – analyse performance, design optimal org structure.
2. General Recruitment – detect gaps, design new Generals with clear missions.
3. General Training – distill critical knowledge, transfer role‑specific skills.
4. Performance Evaluation – monitor impact, retain/retrain/archive.
5. Knowledge Sovereignty – main brain (ceo_library + ceo_memory) is single source of truth.

### STRATEGIC PILLARS
- SEO dominance via long‑tail keywords and topical authority.
- Conversion architecture with PAS/AIDA, performance‑ranked product cards.
- Email list monetization with personalized sequences.
- Multi‑platform distribution (X, LinkedIn, Pinterest, TikTok).
- AI‑first efficiency.
- Organizational self‑design.

### CURRENT GOAL
100,000 monthly visitors at 15% conversion within 12 months, building an autonomous multi‑agent command structure."""

PLATFORM_GUIDE = """
Social media posts per platform:
- X: 280 chars max, 1-2 hashtags.
- LinkedIn: 1300 chars max, headline + question.
- Instagram: 2200 chars, emojis, 3-5 hashtags, "link in bio".
- Pinterest: 500 chars, keyword-rich, call to save.
- Facebook: 1-2 paragraphs, ask a question.
- TikTok: 15-30 sec script, "link in bio".
Append blog URL to all except TikTok/Pinterest."""

# ── STATE MANAGEMENT ───────────────────────────────────────────────────────
state_mgr = AbvornState(STATE_FILE.with_suffix('.db'))
if STATE_FILE.exists():
    state_mgr.import_legacy_json(STATE_FILE)

_state_buffer = None
_last_save = 0
_state_lock = threading.RLock()

DEFAULT_STATE = {
    "queue": [], "completed": [], "failed": [], "deployed": [],
    "performance": {}, "redirects": {}, "model_metrics": [], "email_schedule": [],
    "generals": {}, "enterprise_structure": {}, "cta_variants": {},
    "predictions": {}, "prediction_accuracy": {"total": 0, "correct": 0, "history": []},
    "research_queue": [], "rss_sources": [], "persona_registry": {}
}

def load_state():
    global _state_buffer
    with _state_lock:
        if _state_buffer is not None: return _state_buffer
        _state_buffer = state_mgr.get_meta("full_state", dict(DEFAULT_STATE))
        return _state_buffer

def save_state(state):
    global _state_buffer, _last_save
    with _state_lock:
        _state_buffer = state
        state_mgr.set_meta("full_state", state)
        if time.time() - _last_save > 2: _flush_state()

def prune_state(state):
    if len(state.get('model_metrics', [])) > 100: state['model_metrics'] = state['model_metrics'][-100:]
    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    state['email_schedule'] = [e for e in state.get('email_schedule', []) if e.get('send_at','') > cutoff or e.get('status') == 'scheduled']
    if len(state.get('deployed', [])) > 200: state['deployed'] = state['deployed'][-200:]
    return state

def _flush_state():
    global _state_buffer, _last_save
    with _state_lock:
        if _state_buffer is None: return
        _state_buffer = prune_state(_state_buffer)
        state_mgr.set_meta("full_state", _state_buffer)
        tmp = STATE_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(_state_buffer, indent=2))
        tmp.rename(STATE_FILE)
        _last_save = time.time()

atexit.register(_flush_state)

def _periodic_backup():
    while True:
        time.sleep(300)
        if STATE_FILE.exists():
            backup_dir = BOARDROOM_DIR / "state_backups"
            backup_dir.mkdir(exist_ok=True)
            backup = backup_dir / f"state_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
            shutil.copy2(STATE_FILE, backup)
            for old in sorted(backup_dir.glob("state_*.json"))[:-10]:
                old.unlink()

if not any(t.name == "abvorn_state_backup" for t in threading.enumerate()):
    threading.Thread(target=_periodic_backup, daemon=True, name="abvorn_state_backup").start()

# ── CHROMADB BRAIN ─────────────────────────────────────────────────────────
BOOKS_DIR = pathlib.Path('/content/drive/MyDrive/Notebook LM Brain')
CHROMA_LOCAL = pathlib.Path("/tmp/abvorn_chroma")
CHROMA_LOCAL.mkdir(exist_ok=True)
embed_fn = embedding_functions.DefaultEmbeddingFunction()
db_client = chromadb.PersistentClient(path=str(CHROMA_LOCAL))
library_db = db_client.get_or_create_collection(name="ceo_library", embedding_function=embed_fn)
memory_db = db_client.get_or_create_collection(name="ceo_memory", embedding_function=embed_fn)

def backup_chroma_to_drive():
    try:
        with zipfile.ZipFile(CHROMA_BACKUP_FILE, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in CHROMA_LOCAL.rglob("*"):
                if f.is_file(): zf.write(f, f.relative_to(CHROMA_LOCAL))
        logger.info(f"ChromaDB backed up ({CHROMA_BACKUP_FILE.stat().st_size / 1024:.0f} KB)")
    except Exception as e:
        logger.error(f"ChromaDB backup failed: {e}")

def restore_chroma_from_drive():
    if CHROMA_LOCAL.exists() and any(CHROMA_LOCAL.iterdir()): return
    if CHROMA_BACKUP_FILE.exists():
        try:
            with zipfile.ZipFile(CHROMA_BACKUP_FILE, 'r') as zf:
                zf.extractall(CHROMA_LOCAL)
            logger.info("ChromaDB restored from backup.")
            if PROCESSED_BOOKS_FILE.exists(): PROCESSED_BOOKS_FILE.write_text("{}")
        except Exception as e:
            logger.error(f"ChromaDB restore failed: {e}")

restore_chroma_from_drive()

# ── LIBRARY INDEXING ───────────────────────────────────────────────────────
processed_books = {}
if PROCESSED_BOOKS_FILE.exists():
    try: processed_books = json.loads(PROCESSED_BOOKS_FILE.read_text())
    except: pass

if BOOKS_DIR.exists():
    new_chunks, new_ids, new_meta = [], [], []
    for cat in BOOKS_DIR.iterdir():
        if not cat.is_dir(): continue
        readme = cat / "README.md"
        if readme.exists():
            text = readme.read_text(encoding='utf-8', errors='replace').strip()
            if text:
                new_chunks.append(f"[INSTRUCTION:{cat.name}]\n{text}")
                new_ids.append(f"readme_{cat.name}")
                new_meta.append({"source": f"README.md/{cat.name}", "category": cat.name, "type": "instruction"})
        for book in cat.iterdir():
            if book.suffix.lower() != '.pdf': continue
            bp = str(book); mt = book.stat().st_mtime
            if bp in processed_books and processed_books[bp] >= mt: continue
            try:
                text = "\n".join(p.extract_text() for p in PdfReader(str(book)).pages)
                for i, chunk in enumerate([c.strip() for c in text.split("\n\n") if len(c.strip()) > 50]):
                    new_chunks.append(chunk)
                    new_ids.append(f"{cat.name}_{book.stem}_{i}")
                    new_meta.append({"book": book.stem, "category": cat.name, "type": "pdf_chunk"})
                processed_books[bp] = mt
            except Exception as e:
                logger.warning(f"Failed to ingest PDF '{bp}': {e}")
    if new_chunks:
        logger.info(f"Adding {len(new_chunks)} new chunks...")
        library_db.add(documents=new_chunks, ids=new_ids, metadatas=new_meta)
        PROCESSED_BOOKS_FILE.write_text(json.dumps(processed_books, indent=2))

def load_skills():
    return "\n".join(f"\n--- {s.stem} ---\n{s.read_text()[:2000]}" for s in SKILLS_DIR.glob("*.md"))

MASTER_SKILLS = load_skills()

# ── MEMORY ──────────────────────────────────────────────────────────────────
def add_memory_fact(gap, answer, source="self-reflection"):
    fid = f"mem_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{random.getrandbits(32):08x}"
    try:
        memory_db.add(documents=[gap], ids=[fid], metadatas=[{"answer": answer, "source": source, "timestamp": datetime.now().isoformat()}])
    except Exception as e:
        logger.warning(f"Memory store failed: {e}")

def retrieve_memory_facts(query, top_k=2):
    try:
        if memory_db.count() == 0: return []
        res = memory_db.query(query_texts=[query], n_results=top_k)
        return [{"gap": d, "answer": m.get("answer", ""), "source": m.get("source", "memory")} for d, m in zip(res["documents"][0], res["metadatas"][0])]
    except: return []

# ── AI CLIENTS ──────────────────────────────────────────────────────────────
router = ModelRouter(S)

PEXELS_API_KEY = S["PEXELS_KEY"]

AFFILIATE_NETWORKS = [
    {"name":"Amazon","base_search_url":"https://www.amazon.com/s?k={query}","affiliate_param":"tag","affiliate_id":S["AMAZON_TAG"]},
    {"name":"ShareASale","base_search_url":"https://www.shareasale.com/merchantsearch.cfm?keyword={query}","affiliate_param":"affiliate_id","affiliate_id":S["SHAREASALE_ID"]},
    {"name":"eBay","base_search_url":"https://www.ebay.com/sch/i.html?_nkw={query}&mkcid=1&mkrid=711-53200-19255-0&siteid=0&campid={affiliate_id}&toolid=10001&customid=&mkevt=1","affiliate_id":S["EBAY_CAMPID"]},
]

def ask_ai(prompt, json_mode=False, use_soul=True, model_priority=None):
    system = SOUL if use_soul else None
    return router.ask(prompt, system=system, json_mode=json_mode)

def flush_model_metrics():
    pass

# ── UTILITIES ───────────────────────────────────────────────────────────────
def strict_json(text):
    if not text: return None
    try: return json.loads(text)
    except:
        m = re.search(r'\[.*\]|\{.*\}', text, re.DOTALL)
        if m:
            try: return json.loads(m.group(0))
            except: pass
    fixed = ask_ai(f"Fix this broken JSON. Output ONLY valid JSON: {text}", use_soul=False)
    try: return json.loads(fixed)
    except: return None

def inject_affiliate_link(url, network=None):
    if network and network.get('affiliate_param') and network.get('affiliate_id'):
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}{network['affiliate_param']}={network['affiliate_id']}"
    if "amazon." in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}tag={AFFILIATE_NETWORKS[0]['affiliate_id']}"
    return url

from concurrent.futures import ThreadPoolExecutor, as_completed

def validate_image_fast(url, min_size=5000, max_size_mb=2):
    try:
        h = requests.head(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True)
        if h.status_code != 200 or 'image' not in h.headers.get('Content-Type', ''): return False
        cl = int(h.headers.get('Content-Length', 0))
        return min_size <= cl <= max_size_mb * 1024 * 1024
    except: return False

def fetch_images(query, count=3):
    candidates = []
    try:
        r = requests.get(f"https://api.pexels.com/v1/search?query={quote_plus(query)}&per_page={count*2}", headers={"Authorization": PEXELS_API_KEY}, timeout=10)
        if r.status_code == 200: candidates += [p['src']['large'] for p in r.json().get("photos", [])]
    except: pass
    try:
        with DDGS() as ddgs:
            for r in ddgs.images(query, max_results=count*2):
                url = r.get('image', '')
                if url: candidates.append(url)
    except: pass
    for i in range(count):
        candidates.append(f"https://loremflickr.com/800/600/{quote_plus(query)}?random={i}")
    validated = []
    with ThreadPoolExecutor(max_workers=min(len(candidates), 6)) as ex:
        fut = {ex.submit(validate_image_fast, url): url for url in candidates}
        for f in as_completed(fut):
            if f.result():
                validated.append(fut[f])
                if len(validated) >= count: break
    return validated[:count] if validated else [f"https://via.placeholder.com/800x600?text={quote_plus(query)}"] * count

# ── PERSONA SYSTEM ──────────────────────────────────────────────────────────
def generate_persona_variant(niche_name, products=None, variant="standard"):
    """AI-generates a detailed buyer persona tailored to this niche and product set."""
    prod_str = ", ".join(p.get('name','') for p in (products or [])) if products else niche_name
    prompt = f"""Create a vivid, specific buyer persona for a buying guide about '{niche_name}'.

Products: {prod_str}

This persona will DIRECTLY shape the content — tone, keywords, objections, everything.
Make them feel real with specific details.

Return JSON with EXACTLY these keys:
- persona_id: short unique slug like "quality_seeker" or "budget_minded_parent"
- name: first name
- bio: 1-sentence backstory
- age_range: "25-40"
- occupation: job title
- income_level: "budget-conscious" / "mid-range" / "premium"
- tech_savvy: 1-10
- goals: 3 specific goals this person has
- frustrations: 3 deep frustrations they feel about the problem this niche solves
- fears: 2 fears about choosing wrong
- desires: 2 secret wishes
- decision_criteria: ["price","quality","reviews","brand","features","warranty","design"]
- objections: 2-3 objections to buying
- emotional_journey: "from ___ to ___"
- content_preferences: "detailed guides" / "quick comparisons" / "real stories" / "video reviews"
- tone_of_voice: how to speak to this exact person (e.g. "direct and data-driven" or "warm and reassuring")
- keywords: ["3-5 long-tail keywords this person would search for"]
- tags: ["3-5 relevant tags"]
- preferred_formats: ["comparison tables", "pros/cons lists", "real-world photos", etc]

Variant focus (tilt the persona toward this angle): {variant}"""
    result = strict_json(ask_ai(prompt, json_mode=True))
    if not result or not isinstance(result, dict):
        result = {"persona_id":f"{niche_name[:15].lower().replace(' ','_')}_{variant}","name":"Alex","bio":"Busy professional looking for the best value","age_range":"25-40","occupation":"Professional","income_level":"mid-range","tech_savvy":6,"goals":["Save money","Get quality","Feel confident"],"frustrations":["Too many choices","Bad reviews","Wasting money"],"fears":["Buying wrong","Getting scammed"],"desires":["One clear winner","Honest advice"],"decision_criteria":["quality","reviews","price"],"objections":["Too expensive","Not sure it works"],"emotional_journey":"overwhelmed to confident","content_preferences":"detailed guides","tone_of_voice":"conversational and honest","keywords":[f"best {niche_name}",f"{niche_name} review",f"top {niche_name} 2025"],"tags":[niche_name,"buying guide","review"],"preferred_formats":["comparison tables","pros/cons lists"]}
    return result

def register_persona(niche_name, persona):
    """Store a persona in the registry with fresh performance tracking."""
    state = load_state()
    registry = state.setdefault('persona_registry', {})
    pid = persona.get('persona_id', f"{niche_name.lower().replace(' ','_')[:20]}_{random.getrandbits(16):04x}")
    if pid not in registry:
        registry[pid] = {
            "niche": niche_name, "persona": persona,
            "created": datetime.now().isoformat(),
            "performance": {"impressions": 0, "clicks": 0, "conversions": 0, "avg_quality": 0.0, "post_count": 0},
            "last_used": None
        }
    registry[pid]['last_used'] = datetime.now().isoformat()
    save_state(state)
    return pid

def select_or_evolve_persona(niche_name, products=None):
    """Pick the best-performing persona for this niche, or generate+register a new one if none exist."""
    state = load_state()
    registry = state.get('persona_registry', {})
    niche_personas = {k: v for k, v in registry.items() if v.get('niche') == niche_name}
    variant_labels = ["standard", "budget_focused", "premium_seeker", "first_time_buyer", "tech_enthusiast"]

    if niche_personas:
        used_variants = [v['persona'].get('persona_id','').split('_')[-1] for v in niche_personas.values()]
        unused = [v for v in variant_labels if v not in used_variants]
        # Score by avg_quality * post_count (confidence-weighted)
        best = max(niche_personas.values(), key=lambda p: p['performance'].get('avg_quality', 0) * max(p['performance'].get('post_count', 1), 0.5) if p['performance'].get('post_count', 0) > 0 else -1)
        best_perf = best['performance']
        # If best persona has < 3 posts or quality < 6, generate a new variant
        if best_perf.get('post_count', 0) >= 3 and best_perf.get('avg_quality', 0) >= 6.0:
            return best['persona'], list(niche_personas.keys())[list(niche_personas.values()).index(best)]
        if unused:
            variant = unused[0]
        else:
            variant = f"variant_{len(niche_personas) + 1}"
    else:
        variant = "standard"

    persona = generate_persona_variant(niche_name, products or [], variant=variant)
    pid = register_persona(niche_name, persona)
    return persona, pid

def track_persona_outcome(persona_id, quality_score=0, views=0, users=0):
    """Record content performance back to the persona for evolution."""
    if not persona_id: return
    state = load_state()
    registry = state.get('persona_registry', {})
    if persona_id not in registry: return
    p = registry[persona_id]['performance']
    p['post_count'] = p.get('post_count', 0) + 1
    p['impressions'] = p.get('impressions', 0) + views
    p['clicks'] = p.get('clicks', 0) + users
    if quality_score:
        prev_total = p.get('avg_quality', 0) * (p.get('post_count', 1) - 1)
        p['avg_quality'] = (prev_total + quality_score) / p['post_count']
    p['last_used'] = datetime.now().isoformat()
    save_state(state)

def get_persona_insights(niche_name):
    """Return performance summary of all personas for this niche."""
    state = load_state()
    registry = state.get('persona_registry', {})
    return [(pid, v['persona'].get('name','?'), v['performance']) for pid, v in registry.items() if v.get('niche') == niche_name]

def query_internal_brain(niche_name, keyword, persona=None):
    knowledge = ""
    if persona:
        knowledge = f"Buyer: {persona.get('name', 'Customer')}, pain points: {persona.get('top_3_pain_points', [])}"
    # 1. Library (PDF books)
    try:
        res = library_db.query(query_texts=[f"{niche_name} {keyword} {knowledge}"], n_results=5)
        if res["documents"][0]:
            knowledge += "\n\nLibrary:\n" + "\n".join(f"[{m.get('book','?')}]\n{d[:500]}" for d, m in zip(res["documents"][0], res["metadatas"][0]))
    except: pass
    # 2. Memory (research findings, web results, curiosity gaps)
    try:
        memory = retrieve_memory_facts(f"{niche_name} {keyword}", top_k=3)
        if memory:
            knowledge += "\n\nMemory:\n" + "\n".join(f"- {m.get('answer','')[:300]}" for m in memory)
    except: pass
    # 3. Quick web context
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            for r in ddgs.text(f"{niche_name} {keyword} guide 2025", max_results=3):
                snippet = r.get('body','')[:200]
                if snippet:
                    knowledge += f"\nWeb: {r.get('title','')}: {snippet}"
    except: pass
    return knowledge[:4000]

# ── AI-POWERED PRODUCT GENERATION (replaces scraping) ──────────────────────
def generate_products_for_niche(niche_name, market_context=""):
    """Ask the AI to generate realistic, specific product recommendations."""
    prompt = f"""You are a product research expert. For the niche '{niche_name}', recommend exactly 3 specific products that would appear in an expert buying guide. Use your knowledge of real products and brands.

Return a JSON array. Each product must have:
- name: specific product name with brand and model
- price: realistic price string like "$49.99" or "$249-$399"
- description: 1-2 sentence highlight of what makes it great
- features: array of 3-4 key features
- category: "best_overall", "best_value", or "premium_pick" 
- affiliate_query: short search query for this product (e.g. "Sony+WH-1000XM5")

Example for "wireless headphones":
[
  {{"name": "Sony WH-1000XM5", "price": "$349.99", "description": "Industry-leading noise cancellation with Auto NC Optimizer", "features": ["30-hour battery", "Multipoint connection", "Lightweight design"], "category": "premium_pick", "affiliate_query": "Sony+WH-1000XM5"}},
  {{"name": "Anker Soundcore Space Q45", "price": "$149.99", "description": "Premium ANC at a fraction of the price", "features": ["50-hour battery", "LDAC support", "Foldable design"], "category": "best_overall", "affiliate_query": "Anker+Soundcore+Space+Q45"}},
  {{"name": "Soundcore Life Q30", "price": "$79.99", "description": "Best budget noise-cancelling headphones", "features": ["40-hour battery", "Multipoint", "Comfortable fit"], "category": "best_value", "affiliate_query": "Soundcore+Life+Q30"}}
]

Products should be real, specific, and genuinely useful for someone researching '{niche_name}'.
Market context: {market_context[:500]}
Niche: {niche_name}"""
    result = strict_json(ask_ai(prompt, json_mode=True))
    if not result or not isinstance(result, list):
        result = [{"name": f"Top {niche_name} Pick", "price": "Check Price", "description": f"Best {niche_name} on the market", "features": ["Quality", "Value", "Reliability"], "category": "best_overall", "affiliate_query": niche_name.replace(' ', '+')}]
    for p in result:
        p['affiliate_query'] = p.get('affiliate_query', niche_name.replace(' ', '+'))
    return result

def build_affiliate_url(query, network=None):
    net = network or AFFILIATE_NETWORKS[0]
    url = net['base_search_url'].replace('{query}', query)
    return inject_affiliate_link(url, net)

# ── SCHEMA MARKUP GENERATORS (thin wrappers around abvorn build_schema) ──────
def build_article_schema(title, description, url, image, date_published, author="Abvorn Editorial"):
    s = build_schema(title, description, url, image, date_published, [], [])
    return s.get("article", "{}")

def build_product_schema(products):
    s = build_schema("Products", "", "", "", "", products, [])
    return s.get("product", "{}")

def build_faq_schema(faqs):
    s = build_schema("FAQ", "", "", "", "", [], faqs)
    return s.get("faq", "{}")

def build_breadcrumb_schema(items):
    elements = ",".join(f'{{"@type":"ListItem","position":{i+1},"name":{json.dumps(n)},"item":{json.dumps(u)}}}' for i, (n, u) in enumerate(items))
    return f'{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{elements}]}}'

# ── GA4 ─────────────────────────────────────────────────────────────────────
def send_ga4_event(client_id, event_name, params=None):
    try:
        requests.post(f"https://www.google-analytics.com/mp/collect?measurement_id={GA4_MEASUREMENT_ID}", json={"client_id": client_id, "events": [{"name": event_name, "params": params or {}}], "api_secret": GA4_API_SECRET}, timeout=5)
    except: pass

# ── EMAIL ───────────────────────────────────────────────────────────────────
def send_email(to_email, subject, body_html, niche_name=None, theme=None):
    if SAFE_MODE: return logger.warning("Safe mode: email not sent.") or False
    if not GMAIL_USER or not GMAIL_APP_PASSWORD: return logger.error("Email not configured.") or False
    accent = html_escape(theme.get('accent_color', '#5A7D9A')) if theme else '#5A7D9A'
    body = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f4f4f4;">
    <table width="100%"><tr><td style="background:#000;padding:20px;text-align:center;border-bottom:4px solid {accent};">
    <img src="{LOGO_URL}" alt="Abvorn" style="max-width:120px;"></td></tr>
    <tr><td style="padding:30px;">{body_html}</td></tr></table></body></html>"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = html_escape(subject); msg['From'] = f"Abvorn <{GMAIL_USER}>"; msg['To'] = to_email
        msg.attach(MIMEText(body, 'html', 'utf-8'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30) as s:
            s.login(GMAIL_USER, GMAIL_APP_PASSWORD); s.sendmail(GMAIL_USER, [to_email], msg.as_string())
        send_ga4_event(to_email, "email_sent", {"niche": niche_name or "general"})
        return True
    except Exception as e: logger.error(f"Email failed: {type(e).__name__}"); return False

def validate_email_address(email):
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))

def add_subscriber_to_sheet(email, niche_slug, source="blog_sidebar", lead_magnet="Free Guide"):
    if not validate_email_address(email): return False
    try:
        auth.authenticate_user()
        gc = gspread.authorize(default()[0])
        sh = gc.open_by_key(S["SHEET_ID"])
        try: ws = sh.worksheet(niche_slug)
        except:
            ws = sh.add_worksheet(title=niche_slug, rows="1000", cols="20")
            ws.append_row(["email","niche_slug","source","subscribed_at","status","lead_magnet"])
        if email in ws.col_values(1): return False
        ws.append_row([email, niche_slug, source, datetime.now().isoformat(), "active", lead_magnet])
        return True
    except Exception as e:
        logger.error(f"Sheet error: {e}"); return False

# ── TELEGRAM ────────────────────────────────────────────────────────────────
def notify(message, parse_mode="Markdown", _retry=0):
    MAX_RETRIES = 3
    if not TELEGRAM_TOKEN or "YOUR_TELEGRAM" in TELEGRAM_TOKEN: return False
    if not TELEGRAM_CHAT_ID or "YOUR_" in str(TELEGRAM_CHAT_ID): return False
    if _retry >= MAX_RETRIES: return False
    chat_id = '-' + str(TELEGRAM_CHAT_ID).strip().lstrip('-').lstrip('0') if str(TELEGRAM_CHAT_ID).strip().startswith('-') else str(TELEGRAM_CHAT_ID).strip()
    payload = {"chat_id": chat_id, "text": str(message), "disable_web_page_preview": True}
    if parse_mode not in (None, "None", ""): payload["parse_mode"] = parse_mode
    try:
        resp = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json=payload, timeout=15)
        if resp.status_code == 200: return True
        if resp.status_code == 429:
            time.sleep(min(resp.json().get("parameters", {}).get("retry_after", 10), 30))
            return notify(message, parse_mode=parse_mode, _retry=_retry+1)
        if resp.status_code == 400 and parse_mode != "None":
            return notify(message, parse_mode="None", _retry=_retry+1)
        return False
    except: return False

def telegram_self_test():
    if not TELEGRAM_TOKEN or "YOUR_TELEGRAM" in TELEGRAM_TOKEN: return logger.warning("Telegram not configured.") or False
    try:
        r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe", timeout=10)
        if not (r.status_code == 200 and r.json().get("ok")): return False
        bot_name = r.json()["result"].get("username", "bot")
    except: return False
    ok = notify(f"Abvorn self-test: {bot_name} online.", parse_mode="None")
    logger.info("Telegram self-test PASSED" if ok else "Telegram self-test FAILED")
    return ok

telegram_self_test()

def _periodic_chroma_backup():
    while True: time.sleep(600); backup_chroma_to_drive()

if not any(t.name == "abvorn_chroma_backup" for t in threading.enumerate()):
    threading.Thread(target=_periodic_chroma_backup, daemon=True, name="abvorn_chroma_backup").start()

# ── PREDICTIVE NICHE FUTURES MARKET ────────────────────────────────────────
def record_prediction(niche_name, expected_conversions=0, expected_traffic=0, market_context=""):
    state = load_state()
    pred = {
        "niche": niche_name, "timestamp": datetime.now().isoformat(),
        "expected_conversions": expected_conversions, "expected_traffic": expected_traffic,
        "actual_conversions": None, "actual_traffic": None,
        "market_context": market_context[:200], "resolved": False
    }
    state.setdefault("predictions", {})[niche_name] = pred
    save_state(state)
    return pred

def resolve_prediction(niche_name, actual_conversions, actual_traffic=0):
    state = load_state()
    preds = state.get("predictions", {})
    if niche_name not in preds: return
    pred = preds[niche_name]
    pred["actual_conversions"] = actual_conversions
    pred["actual_traffic"] = actual_traffic
    pred["resolved"] = True
    accuracy = state.setdefault("prediction_accuracy", {"total": 0, "correct": 0, "history": []})
    accuracy["total"] += 1
    if pred.get("expected_conversions", 0) > 0:
        margin = abs(actual_conversions - pred["expected_conversions"]) / max(pred["expected_conversions"], 1)
        if margin < 0.5: accuracy["correct"] += 1
    accuracy["history"].append({
        "niche": niche_name, "expected": pred["expected_conversions"],
        "actual": actual_conversions, "timestamp": datetime.now().isoformat()
    })
    save_state(state)

# ── ENTERPRISE ARCHITECTURE & GENERALS ─────────────────────────────────────
def design_enterprise_structure(state):
    perf = state.get('performance', {})
    top = sorted(((s, d) for s, d in perf.items() if isinstance(d, dict)), key=lambda kv: kv[1].get('conversions', 0), reverse=True)[:5]
    gens = state.get('generals', {})
    prompt = f"""Analyse Abvorn Empire state and design the optimal organizational structure.
Top niches: {json.dumps(top)}
Active Generals: {list(gens.keys()) if gens else 'None'}
Deployed: {len(state.get('deployed', []))}, Failed: {len(state.get('failed', []))}

Identify capability gaps and which new Generals are needed.

Output JSON:
{{"structure":{{"name":"Phase name","division":"content/design/growth/distribution/security","roles":[{{"title":"Role","general_name":"gen name or none","responsibilities":["..."]}}],"reporting_lines":["role->role"]}},"gaps_detected":["gap1"],"recommended_new_generals":[{{"name":"General Name","domain":"domain","reason":"why"}}]}}"""
    result = strict_json(ask_ai(prompt, json_mode=True))
    if not result:
        result = {"structure":{"name":"Initial phase","division":"content","roles":[],"reporting_lines":[]},"gaps_detected":[],"recommended_new_generals":[]}
    state['enterprise_structure'] = result
    save_state(state)
    return result

def activate_general_persuasion():
    state = load_state()
    if 'general_persuasion' in state.get('generals', {}): return state['generals']['general_persuasion']

    logger.info("Activating General of Persuasion...")
    try:
        general_db = db_client.get_or_create_collection(name="general_persuasion", embedding_function=embed_fn)
    except: general_db = None

    soul = """You are the General of Persuasion for the Abvorn Empire.
Your mission: ensure every word we publish builds trust, intensifies desire, and drives action.
Principles: 1. The reader is emotional first, rational second. 2. Every sentence earns the next.
3. Specificity sells. "Save 37% in 14 days" beats "Save money."
4. Social proof is your strongest weapon. 5. Scarcity must be real, never fabricated."""
    (SKILLS_DIR / "general_persuasion_soul.md").write_text(soul)

    if general_db is not None:
        try:
            res = library_db.query(query_texts=["persuasion copywriting conversion psychology trust desire action"], n_results=100)
            for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
                general_db.add(documents=[doc], ids=[f"distilled_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{random.getrandbits(32):08x}"], metadatas=[{"source": meta.get("book", "ceo_library"), "category": meta.get("category", "unknown"), "type": "distilled_chunk"}])
        except Exception as e:
            logger.warning(f"Distillation failed: {e}")

        for cat_name in ["Copywriting", "Psychology"]:
            rf = BOOKS_DIR / cat_name / "README.md"
            if rf.exists():
                try:
                    text = rf.read_text(encoding='utf-8', errors='replace').strip()
                    if text:
                        general_db.add(documents=[f"[INSTRUCTION:{cat_name}]\n{text}"], ids=[f"readme_{cat_name}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"], metadatas=[{"source": f"README.md/{cat_name}", "category": cat_name, "type": "readme"}])
                except: pass

    info = {"name":"General of Persuasion","collection":"general_persuasion","status":"active","activated":datetime.now().isoformat(),"soul_file":"general_persuasion_soul.md","performance":{"cycles_active":0,"conversion_impact":0,"skills_proposed":0},"domain":"persuasion, copywriting, conversion"}
    state['generals']['general_persuasion'] = info
    save_state(state)
    return info

def train_general(general_name, training_topics):
    state = load_state()
    if general_name not in state.get('generals', {}): return False
    gen = state['generals'][general_name]
    try:
        general_db = db_client.get_collection(name=gen.get('collection', general_name), embedding_function=embed_fn)
    except: return False
    for topic in training_topics[:5]:
        try:
            res = library_db.query(query_texts=[topic], n_results=10)
            for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
                general_db.add(documents=[doc], ids=[f"trained_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{random.getrandbits(32):08x}"], metadatas=[{"source": meta.get("book", "ceo_library"), "category": meta.get("category", "unknown"), "type": "training_chunk", "topic": topic}])
        except: pass
        time.sleep(0.5)
    gen['performance']['last_trained'] = datetime.now().isoformat()
    save_state(state)
    return True

def evaluate_general_performance(general_name, metrics=None):
    state = load_state()
    if general_name not in state.get('generals', {}): return None
    gen = state['generals'][general_name]
    if metrics: gen['performance'].update(metrics)
    result = strict_json(ask_ai(f"Evaluate General '{gen['name']}' (domain: {gen.get('domain','?')}). Data: {json.dumps(gen['performance'])}. Decision: keep/retrain/archive? Output JSON: {{\"decision\":\"keep/retrain/archive\",\"reason\":\"...\",\"recommended_training_topics\":[...]}}", json_mode=True))
    if not result: result = {"decision":"keep","reason":"insufficient data","recommended_training_topics":[]}
    if result['decision'] == 'retrain' and result.get('recommended_training_topics'): train_general(general_name, result['recommended_training_topics'])
    if result['decision'] == 'archive': gen['status'] = 'archived'; gen['archived_at'] = datetime.now().isoformat()
    gen['performance']['last_evaluation'] = datetime.now().isoformat()
    gen['performance']['evaluation_decision'] = result['decision']
    save_state(state)
    return result

def spawn_general_if_needed(state):
    generals = state.get('generals', {})
    enterprise = state.get('enterprise_structure', {})
    recommended = enterprise.get('recommended_new_generals', [])
    if not recommended:
        perf = state.get('performance', {})
        result = strict_json(ask_ai(f"Active Generals: {list(generals.keys()) if generals else 'None'}. Deployed: {len(state.get('deployed',[]))}. Performance: {json.dumps({k:v.get('conversions',0) if isinstance(v,dict) else 0 for k,v in perf.items()})}. Identify if a critical capability gap requires a new General. Output JSON: {{\"needed\":true/false,\"general_design\":{{\"name\":\"General of X\",\"collection_name\":\"general_x\",\"domain\":\"domain\",\"mission\":\"...\",\"principles\":[\"...\"],\"goals\":[\"...\"],\"operating_procedures\":[\"...\"]}},\"reason\":\"...\"}}", json_mode=True))
    else:
        rec = recommended[0]
        result = {"needed":True,"general_design":{"name":rec.get("name",f"General of {rec.get('domain','Unknown')}"),"collection_name":f"general_{rec.get('domain','unknown').lower().replace(' ','_')}","domain":rec.get("domain","general"),"mission":f"Own the {rec.get('domain','domain')} domain","principles":["Data-driven","Continuous improvement"],"goals":["Establish best practices","Improve 10%/cycle"],"operating_procedures":["Analyse","Propose","Report"]},"reason":rec.get("reason","Enterprise analysis")}
    if not result or not result.get('needed'): return None
    d = result['general_design']
    name = d['name'].replace(' ','_').lower()
    if name in generals: return name
    try:
        new_db = db_client.get_or_create_collection(name=d['collection_name'], embedding_function=embed_fn)
    except: return None
    soul = f"You are {d['name']} for Abvorn.\nMission: {d['mission']}\n\nPrinciples:\n" + "\n".join(f"{i+1}. {p}" for i,p in enumerate(d.get('principles',['Excellence']))) + "\n\nGoals:\n" + "\n".join(f"- {g}" for g in d.get('goals',['Improve performance'])) + "\n\nProcedures:\n" + "\n".join(f"- {p}" for p in d.get('operating_procedures',['Analyse and report']))
    (SKILLS_DIR / f"{d['collection_name']}_soul.md").write_text(soul)
    try:
        res = library_db.query(query_texts=[d['domain']], n_results=50)
        for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
            new_db.add(documents=[doc], ids=[f"seed_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{random.getrandbits(32):08x}"], metadatas=[{"source":meta.get("book","ceo_library"),"category":meta.get("category","unknown"),"type":"initial_seed"}])
    except: pass
    state['generals'][name] = {"name": d['name'], "collection": d['collection_name'], "status":"active","activated":datetime.now().isoformat(),"soul_file":f"{d['collection_name']}_soul.md","performance":{"cycles_active":0,"conversion_impact":0,"skills_proposed":0},"domain":d['domain'],"design_params":d}
    save_state(state)
    msg = f"New General spawned: {d['name']} (domain: {d['domain']})"
    notify(msg); logger.info(msg)
    return name

# ── RECURSIVE QUERY CHAIN ─────────────────────────────────────────────────────
# Captain → General → Brain (CEO Library + CEO Memory + Web Research)
# Each level escalates to parent when confidence is low. Brain actively researches.

WEB_RESEARCH_LOG = []  # tracks URLs fetched this run to avoid re-pulling

def brain_research(question, top_k=3):
    """Search the web and store findings in CEO Memory for persistent growth.
    Returns enriched knowledge string from ChromaDB + fresh web results."""
    knowledge = ""

    # 1. Query existing ChromaDB (library + memory)
    try:
        res = library_db.query(query_texts=[question], n_results=top_k)
        if res["documents"][0]:
            knowledge += "Library:\n" + "\n".join(f"- {d[:300]}" for d in res["documents"][0])
    except: pass
    memory = retrieve_memory_facts(question, top_k=top_k)
    if memory:
        knowledge += "\nMemory:\n" + "\n".join(f"- {m.get('answer','')[:200]}" for m in memory)

    # 2. Web research — always search for fresh material
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(question, max_results=5))
            # Also search a related practical query
            results += list(ddgs.text(f"{question} guide tips 2025", max_results=3))
            # Filter out already-seen URLs this session
            fresh = [r for r in results if r.get('href','') not in WEB_RESEARCH_LOG]
            for r in fresh:
                WEB_RESEARCH_LOG.append(r.get('href',''))
                title = r.get('title','')
                snippet = r.get('body','')
                # Store into memory for future runs
                add_memory_fact(
                    f"Web research: {title}",
                    f"{snippet[:500]} — Source: {r.get('href','')}",
                    source="web_research"
                )
            if fresh:
                knowledge += "\nWeb:\n" + "\n".join(
                    f"- {r['title']}: {r.get('body','')[:200]}" for r in fresh
                )
    except Exception as e:
        pass  # web search is best-effort

    return knowledge[:2500] if knowledge else ""

def _query_brain(question, top_k=3):
    """Query brain with full research loop: ChromaDB + web. Seeds memory."""
    return brain_research(question, top_k)

def _query_collection(collection_name, question, top_k=5):
    """Query a specific ChromaDB collection."""
    try:
        col = db_client.get_collection(name=collection_name, embedding_function=embed_fn)
        res = col.query(query_texts=[question], n_results=top_k)
        if res["documents"][0]:
            return "\n".join(f"- {d[:300]}" for d in res["documents"][0])
    except: pass
    return ""

def general_query(general_name, question):
    """General queries own DB → escalates to Brain when uncertain.
    Returns answer and whether it needed to escalate."""
    state = load_state()
    gen = state.get('generals', {}).get(general_name)
    if not gen: return _query_brain(question), True
    collection_name = gen.get('collection', general_name)
    own_knowledge = _query_collection(collection_name, question)
    if own_knowledge:
        prompt = f"As {gen.get('name', 'General')}, answer using your knowledge. Question: {question}\nYour knowledge: {own_knowledge[:1500]}"
        answer = ask_ai(prompt, use_soul=False)
        if answer and len(answer) > 20: return answer, False
    # Escalate to Brain
    brain_knowledge = _query_brain(question)
    prompt = f"As {gen.get('name', 'General')}, you needed to consult the Brain. Question: {question}\nBrain knowledge: {brain_knowledge[:1500]}"
    answer = ask_ai(prompt, use_soul=False) or "Consulting Brain..."
    add_memory_fact(f"General {general_name} queried Brain about: {question[:100]}", answer[:200], source=f"general_query")
    return answer, True

def captain_query(general_name, platform, question):
    """Captain queries General → General may escalate to Brain.
    The Captain gets the answer PLUS an explanation of where it came from."""
    state = load_state()
    gen = state.get('generals', {}).get(general_name)
    if not gen: return _query_brain(question), "brain (no general found)"
    captain = gen.get('captains', {}).get(platform)
    if not captain: return general_query(general_name, question)
    # Captain knowledge chunks
    chunks = captain.get('knowledge_chunks', [])
    if chunks:
        chunk_text = "\n".join(f"- {c[:250]}" for c in chunks[:5])
        prompt = f"As {captain.get('name', 'Captain of ' + platform)}, answer using your training. Question: {question}\nYour knowledge: {chunk_text[:1500]}"
        answer = ask_ai(prompt, use_soul=False)
        if answer and len(answer) > 20: return answer, "captain"
    # Escalate to General
    answer, escalated = general_query(general_name, question)
    source = "general" if not escalated else "general→brain"
    return answer, source

# ── CAPTAIN SYSTEM ───────────────────────────────────────────────────────────
SOCIAL_PLATFORMS = ["x", "instagram", "linkedin", "facebook", "tiktok"]

def spawn_captain(general_name, platform, label):
    """Spawn a Captain under a General for a specific platform."""
    state = load_state()
    generals = state.get('generals', {})
    if general_name not in generals: return None
    gen = generals[general_name]
    captains = gen.setdefault('captains', {})
    if platform in captains: return captains[platform]
    captain = {
        "name": f"Captain of {label}",
        "platform": platform, "status": "active",
        "activated": datetime.now().isoformat(),
        "performance": {"posts": 0, "engagement": 0, "follows": 0, "last_post": None},
        "training_log": [], "queries_escalated": 0, "queries_answered": 0
    }
    gen['captains'][platform] = captain
    save_state(state)
    msg = f"Captain spawned: Captain of {label} under {gen['name']}"
    notify(msg); logger.info(msg)
    return captain

def train_captain(general_name, platform, topics=None):
    """Train a Captain from the General's knowledge base."""
    state = load_state()
    gen = state.get('generals', {}).get(general_name)
    if not gen: return False
    captain = gen.get('captains', {}).get(platform)
    if not captain: return False
    try:
        general_db = db_client.get_collection(name=gen.get('collection', general_name), embedding_function=embed_fn)
    except: return False
    domain_queries = topics or [f"{platform} social media marketing", f"{platform} content strategy", f"engaging {platform} posts"]
    trained = 0
    for query in domain_queries[:3]:
        try:
            res = general_db.query(query_texts=[query], n_results=10)
            for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
                captain.setdefault('knowledge_chunks', []).append(doc[:200])
                trained += 1
        except: pass
        time.sleep(0.3)
    captain['training_log'].append({"timestamp": datetime.now().isoformat(), "chunks_trained": trained, "topics": domain_queries})
    save_state(state)
    logger.info(f"Captain of {platform} trained with {trained} chunks from {gen['name']}")
    return True

def evaluate_captain(general_name, platform):
    """Evaluate a Captain and report back to the General."""
    state = load_state()
    gen = state.get('generals', {}).get(general_name)
    if not gen: return None
    captain = gen.get('captains', {}).get(platform)
    if not captain: return None
    perf = captain.get('performance', {})
    escalation_rate = captain.get('queries_escalated', 0) / max(captain.get('queries_answered', 1), 1)
    eval_data = f"posts={perf.get('posts',0)}, escalation_rate={escalation_rate:.0%}, knowledge_chunks={len(captain.get('knowledge_chunks',[]))}"
    result = strict_json(ask_ai(f"Evaluate Captain of {platform} under {gen['name']}. Performance: {eval_data}. Decision: keep/retrain/archive? Output JSON: {{\"decision\":\"keep/retrain/archive\",\"reason\":\"...\",\"recommended_training\":[...]}}", json_mode=True))
    if not result: result = {"decision":"keep","reason":"insufficient data","recommended_training":[]}
    if result['decision'] == 'retrain' and result.get('recommended_training'):
        train_captain(general_name, platform, result['recommended_training'])
    if result['decision'] == 'archive':
        captain['status'] = 'archived'
        captain['archived_at'] = datetime.now().isoformat()
    captain['last_evaluation'] = result['decision']
    save_state(state)
    logger.info(f"Captain of {platform} evaluated: {result['decision']}")
    return result

def captain_execute(general_name, platform, action_type, params=None):
    """Execute an action through a Captain (used by Cell 3 for social posting)."""
    state = load_state()
    gen = state.get('generals', {}).get(general_name)
    if not gen: return None
    captain = gen.get('captains', {}).get(platform)
    if not captain: return None
    if captain.get('status') == 'archived': return None
    captain['performance']['posts'] = captain['performance'].get('posts', 0) + 1
    captain['performance']['last_post'] = datetime.now().isoformat()
    if params: captain.setdefault('action_log', []).append({"action": action_type, "params": params, "timestamp": datetime.now().isoformat()})
    gen['performance']['cycles_active'] = gen['performance'].get('cycles_active', 0) + 1
    save_state(state)
    return True

# ── INIT ────────────────────────────────────────────────────────────────────
print("   Scanning for broken niches...")
state = load_state()
queued = {q['slug'] for q in state.get('queue', [])}
for slug in list(state.get('failed', [])):
    if state['failed'].count(slug) >= 2 and slug not in queued:
        state['failed'] = [s for s in state['failed'] if s != slug]
        f = EMPIRE_DIR / slug
        if f.exists(): shutil.rmtree(f)
        state['queue'].append({"slug": slug, "niche": slug.replace('_',' ').title(), "stage": "start"})
        queued.add(slug)
for slug in list(state.get('deployed', [])):
    f = EMPIRE_DIR / slug
    if (not f.exists() or not list(f.glob("*.html"))) and slug not in queued:
        state['deployed'] = [s for s in state['deployed'] if s != slug]
        state['queue'].append({"slug": slug, "niche": slug.replace('_',' ').title(), "stage": "start"})
        queued.add(slug)

if not state['queue'] and not state.get('completed') and not state.get('deployed'):
    for seed_slug in ["wireless_headphones", "standing_desk", "coffee_maker"]:
        if seed_slug not in queued:
            state['queue'].append({"slug": seed_slug, "niche": seed_slug.replace('_',' ').title(), "stage": "products"})
            queued.add(seed_slug)
    print(f"   Seeded {len(state['queue'])} starter niche(s).")

activate_general_persuasion()
design_enterprise_structure(state)

# ── PROCESS RESEARCH QUEUE (Curiosity Loop) ──
pending = state.get('research_queue', [])
if pending:
    print(f"   Brain researching {len(pending)} curiosity gap(s)...")
    kept = []
    for item in pending:
        q = item.get('question', '')
        if not q: continue
        knowledge = brain_research(q, top_k=2)
        if knowledge:
            print(f"     \u2705 Researched: {q[:60]}...")
        else:
            kept.append(item)  # retry next cycle if no results
    state['research_queue'] = kept
    print(f"   Research queue: {len(pending) - len(kept)} resolved, {len(kept)} pending")

save_state(state)
print("Abvorn Kernel v13 Online. Enterprise Architecture loaded. Generals system ready.")
