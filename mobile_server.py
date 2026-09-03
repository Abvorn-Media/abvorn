"""Abvorn Mobile Server — PWA-backed AI command center accessible from phone."""

import os, sys, json, subprocess, logging, shlex, asyncio, re, hmac
from pathlib import Path
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from abvorn.core.console_dashboard import get_system_status, generate_dashboard_html

from abvorn.core.secrets import load_secrets
from abvorn.core.models import ModelRouter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("mobile_server")

PROJECT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = PROJECT_DIR / "mobile_server" / "static"
HISTORY_FILE = PROJECT_DIR / "mobile_server" / "chat_history.json"

secrets = load_secrets()
router = ModelRouter(secrets, timeout=25)

app = FastAPI(title="Abvorn Mobile Server", version="1.0.0")

# Optional auth: set ABVORN_API_TOKEN (env or secrets) to protect /api/*.
# Public (unauthenticated) API routes — must be safe to expose.
PUBLIC_API_PATHS = {
    "/api/health", "/api/newsletter/subscribe", "/api/content/recent",
    "/api/entitlements/pending", "/api/entitlements/audit", "/api/surplus",
    "/api/dashboard/metrics",
}

_API_TOKEN = os.environ.get("ABVORN_API_TOKEN", "") or secrets.get("ABVORN_API_TOKEN", "")

# Defense-in-depth: the most dangerous endpoints (arbitrary shell execution and
# arbitrary file writes) are masked UNLESS explicitly opted in at startup, even
# when a token is set. A leaked/weak token must not expose remote code execution.
_ALLOW_EXEC = os.environ.get("ABVORN_ALLOW_EXEC", "").lower() in ("1", "true", "yes")
SENSITIVE_MASKED_PATHS = {"/api/exec", "/api/write"}


# Security-context diagnostics. If no token is configured, the API is open to
# anyone who can reach it — this must be loud, not silent.
if not _API_TOKEN:
    logger.warning(
        "ABVORN_API_TOKEN is NOT set — /api/* is entirely unauthenticated. "
        "Do NOT expose this server beyond localhost."
    )
if not _ALLOW_EXEC:
    logger.warning(
        "Sensitive endpoints %s are MASKED (403) until ABVORN_ALLOW_EXEC=1 is set.",
        sorted(SENSITIVE_MASKED_PATHS),
    )


@app.middleware("http")
async def require_auth(request: Request, call_next):
    path = request.url.path.split("?")[0]

    # 1. Sensitive endpoints are always masked unless explicitly opted in.
    if path in SENSITIVE_MASKED_PATHS and not _ALLOW_EXEC:
        return JSONResponse(
            {"error": "Forbidden: endpoint masked; set ABVORN_ALLOW_EXEC=1 to enable"},
            status_code=403,
        )

    # 2. Everything else under /api/* fails closed: a missing token means the
    #    route is NOT silently public. Only whitelisted public paths may open.
    if path.startswith("/api/"):
        if path in PUBLIC_API_PATHS:
            return await call_next(request)
        if not _API_TOKEN:
            return JSONResponse(
                {"error": "Server misconfigured: ABVORN_API_TOKEN not set; API disabled"},
                status_code=503,
            )
        auth = request.headers.get("Authorization", "")
        expected = f"Bearer {_API_TOKEN}"
        if not auth.startswith("Bearer "):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        supplied = auth[len("Bearer "):]
        if not hmac.compare_digest(supplied, _API_TOKEN):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

chat_history = []
if HISTORY_FILE.exists():
    try:
        chat_history = json.loads(HISTORY_FILE.read_text())
    except Exception:
        chat_history = []

SYSTEM_PROMPT = r"""You are Abvorn's AI, embedded in a product review content ecosystem. You run on a Windows machine in C:\Users\Jean Mare\Documents\Default Project.

You have direct access to:
1. The full project codebase (Python files, HTML templates, docs)
2. Command execution (run any shell command in the project directory)
3. File reading/writing capabilities

PROJECT CONTEXT:
- We build an API-free content ecosystem for Abvorn product reviews
- 10 niches: wireless-headphones, gaming-mice, 4k-monitors, laptops, streaming-devices, mechanical-keyboards, wireless-earbuds, fitness-trackers, webcams, smart-home
- Core AI signals: CI (Contrarian Index), EAS (Emotional Arc Score), SSI (Silent Signal Index), RV (Regret Velocity)
- NDC 2.0 pipeline with ChromaDB knowledge base and analytics bridge
- All AI via free Kilo Gateway models (Qwen, Gemini, Groq, DeepSeek)
- Content builds to docs/ folder, deployable to GitHub Pages
- The user is in China — prefer providers that work well there (Qwen/dashscope, DeepSeek)

When the user asks you to do something:
1. If it's a question, answer from your knowledge
2. If it's a command or task, explain what you'll do, then execute it
3. Show command output clearly
4. Ask clarifying questions when needed

Keep responses concise and action-oriented. You can run python scripts, read/write files, and manage the project."""


class ChatMessage(BaseModel):
    message: str
    stream: bool = False


class CommandRequest(BaseModel):
    command: str
    cwd: Optional[str] = None


class FileRequest(BaseModel):
    path: str
    content: Optional[str] = None


@app.get("/")
async def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/health")
async def health():
    h = router.health()
    return {
        "status": "ok" if h["healthy"] else "degraded",
        "providers": h,
        "project": "Abvorn Content Ecosystem",
        "niches": ["wireless-headphones", "gaming-mice", "4k-monitors", "laptops",
                   "streaming-devices", "mechanical-keyboards", "wireless-earbuds",
                   "fitness-trackers", "webcams", "smart-home"],
        "chat_history": len(chat_history),
    }


@app.get("/api/providers")
async def provider_stats():
    return {"providers": router.get_stats()}


@app.get("/api/priceghost/health")
async def priceghost_health():
    try:
        from src.priceghost_client import get_priceghost
        client = get_priceghost()
        return client.health()
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}


@app.get("/api/win/health")
async def win_health():
    """win.sh loop status for the Relentless Core dashboard."""
    try:
        from abvorn.core.win_sh_bridge import get_win_sh_bridge
        bridge = get_win_sh_bridge()
        return {
            "status": "ok" if bridge.is_ready() else "no_loops",
            "metrics": bridge.get_all_metrics(),
        }
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}


@app.get("/api/dashboard/metrics")
async def dashboard_metrics():
    """Return JSON metrics for the command center dashboard."""
    return get_system_status()


@app.get("/dashboard")
async def dashboard_page():
    """Serve the Abvorn Console HTML dashboard."""
    html = generate_dashboard_html()
    return HTMLResponse(content=html, media_type="text/html")


@app.get("/click/{article_id}/{product_index}")
@app.get("/click/{article_id}")
async def click_redirect(article_id: str, product_index: int = 0, request: Request = None):
    """Track an affiliate click and 302-redirect to the real Amazon URL.

    Articles are rewritten at build time so every Amazon link points at
    /click/<article_id>/<product_index>. The real URL is resolved from the
    click_targets table (populated by rewrite_affiliate_urls) and logged
    before redirecting. Logging is fire-and-forget so the redirect never
    waits on the SQLite write. This endpoint is intentionally public (not
    under /api/), so it is exempt from bearer-token auth.
    """
    from src.click_tracker import log_click, resolve_product_url

    import hashlib, uuid

    url = resolve_product_url(article_id, product_index)
    used_fallback = not url
    if not url:
        tag = secrets.get("AMAZON_TAG", "viraltestco-20")
        query = re.sub(r"-\d+$", "", article_id).replace("-", "+")
        url = f"https://www.amazon.com/s?k={query}&tag={tag}"

    ua = request.headers.get("User-Agent", "") if request is not None else ""
    salt = hashlib.sha1(uuid.uuid4().hex.encode()).hexdigest()[:8]
    ip_hash = ""
    if request is not None and request.client is not None:
        ip_hash = hashlib.sha256(f"{salt}:{request.client.host}".encode()).hexdigest()[:32]

    async def _log_in_background():
        try:
            log_click(article_id, url, user_agent=ua, ip_hash=ip_hash, used_fallback=used_fallback)
        except Exception as e:
            logger.warning("click log failed for %s: %s", article_id, e)

    loop = asyncio.get_event_loop()
    loop.create_task(_log_in_background())

    return RedirectResponse(url, status_code=302)


# ── Symbiotic Cortex (Obsidian) API endpoints ───────────────────────
@app.get("/api/cortex/status")
async def cortex_status():
    """Cortex watcher status and vault path."""
    from abvorn.core.cortex_watcher import cortex_status as get_cortex_status

    return get_cortex_status()


@app.get("/api/cortex/recent")
async def cortex_recent(limit: int = 10):
    """Get the most recent Evolution Journal entries from the vault."""
    from abvorn.core.cortex_watcher import get_recent_journal

    return {"entries": get_recent_journal(limit)}


# ── Google Search Console API endpoints ─────────────────────────────
@app.get("/api/gsc/summary")
async def get_gsc_summary():
    """Get GSC summary stats."""
    from abvorn.core.gsc_client import GSCClient

    return GSCClient().get_summary()


@app.get("/api/gsc/top")
async def get_gsc_top(days: int = 30, limit: int = 20):
    """Get top performing content."""
    from abvorn.core.gsc_client import GSCClient

    client = GSCClient()
    if not client.enabled:
        return {"error": "GSC Client disabled"}
    return {"top_content": client.fetch_top_performing(days, limit)}


@app.get("/api/gsc/opportunities")
async def get_gsc_opportunities(days: int = 30):
    """Get growth opportunities."""
    from abvorn.core.gsc_client import GSCClient

    client = GSCClient()
    if not client.enabled:
        return {"error": "GSC Client disabled"}
    return {"opportunities": client.fetch_growth_opportunities(days)}


@app.post("/api/gsc/ingest")
async def trigger_gsc_ingest(days: int = 7):
    """Manually trigger GSC data ingestion."""
    from abvorn.core.gsc_ingestor import GSCIngestor

    return GSCIngestor().ingest_performance(days)


# ── Evolution Stack API endpoints ──────────────────────────────────
@app.get("/api/evolution/public")
async def evolution_public():
    """Public Evolution Journal payload for the journal page.

    Returns {summary: {current_generation, total_entries, graph_nodes,
    graph_edges, last_update}, entries: [{timestamp, generation, narrative}]}.
    Reads real local sources: the Obsidian vault journal, the Genesis lineage
    file, and the Neural Memory state file. Never raises.
    """
    try:
        from src.deployment import load_evolution_snapshot

        return load_evolution_snapshot()
    except Exception as e:
        logger.warning("evolution/public failed: %s", e)
        return {
            "summary": {
                "current_generation": 1,
                "total_entries": 0,
                "graph_nodes": 0,
                "graph_edges": 0,
                "last_update": None,
            },
            "entries": [],
        }


@app.get("/api/subscribers")
async def get_subscribers():
    """Return all subscribers from the unified database."""
    import sqlite3
    from abvorn.core.unified_database import get_unified_db

    db = get_unified_db()
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscribers")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return {"subscribers": [dict(zip(columns, row)) for row in rows]}


@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """Summary stats from the unified database."""
    from abvorn.core.unified_database import get_unified_db

    return get_unified_db().get_summary()


@app.get("/api/dashboard/charts")
async def get_dashboard_charts():
    """Generate dashboard charts and return them as base64 data URIs."""
    import base64
    from abvorn.core.data_visualizer import DataVisualizer

    viz = DataVisualizer()
    charts = viz.generate_all_charts()
    encoded = {}
    for name, path in charts.items():
        if not path:
            encoded[name] = None
            continue
        try:
            p = Path(path)
            if p.exists():
                b64 = base64.b64encode(p.read_bytes()).decode("ascii")
                encoded[name] = f"data:image/png;base64,{b64}"
            else:
                encoded[name] = None
        except Exception as e:
            logger.warning(f"Could not encode chart {name}: {e}")
            encoded[name] = None
    return {"charts": encoded}


@app.get("/api/price-alerts")
async def get_price_alerts():
    """Return all price alerts from the unified database."""
    import sqlite3
    from abvorn.core.unified_database import get_unified_db

    db = get_unified_db()
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM price_alerts")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return {"alerts": [dict(zip(columns, row)) for row in rows]}


@app.post("/api/sync-listmonk")
async def sync_listmonk():
    """Sync subscribers from Listmonk into the unified database."""
    from abvorn.core.unified_database import get_unified_db
    from abvorn.core.listmonk_client import get_listmonk

    db = get_unified_db()
    listmonk = get_listmonk()
    db.sync_subscribers_from_listmonk(listmonk)
    return {"status": "synced"}


@app.post("/api/send-price-alerts")
async def send_price_alerts():
    """Send any triggered price alerts."""
    from abvorn.core.email_scheduler import EmailScheduler

    scheduler = EmailScheduler()
    scheduler.send_price_alert_emails()
    return {"status": "sent"}


@app.get("/api/memory")
async def get_memory_state():
    """Return the neural memory state."""
    from abvorn.core.neural_memory import get_neural_memory

    memory = get_neural_memory()
    return memory.get_state()


@app.get("/api/spawn")
async def get_spawn_state():
    """Return the spawn controller state."""
    from abvorn.core.spawn_controller import SpawnController

    spawn = SpawnController()
    return spawn.get_state()


@app.get("/api/lineage")
async def get_lineage():
    """Return the Genesis Protocol lineage."""
    from abvorn.core.genesis_protocol import GenesisProtocol

    genesis = GenesisProtocol()
    return genesis.get_lineage()


@app.get("/api/brain")
async def get_brain_state():
    """Return the Brain library status + category report."""
    from abvorn.core.brain import get_brain

    try:
        brain = get_brain()
        return {
            "status": "ready" if brain.is_ready else "building",
            "categories": brain.get_category_report(),
            "entities": brain.memory.get_state().get("entities", 0),
            "is_ready": brain.is_ready,
        }
    except Exception as e:
        return {"status": "unavailable", "categories": {}, "error": str(e)}


# ── Hindsight Reflection API endpoints ──────────────────────────────
@app.get("/api/reflections")
async def get_reflections(limit: int = 10):
    """Return the most recent hindsight reflections from the unified DB."""
    from abvorn.core.learner import HindsightLearner

    learner = HindsightLearner()
    return {"reflections": learner.reflection_store.get_recent(limit)}


@app.get("/api/reflections/summary")
async def get_reflection_summary():
    """Return a platform breakdown of hindsight reflections."""
    from abvorn.core.learner import HindsightLearner

    learner = HindsightLearner()
    return learner.reflection_store.get_summary()


@app.get("/api/content/recent")
async def get_content_recent(limit: int = 10):
    """Return the most recent deployed content from cycle_state.json."""
    import json as _json

    try:
        state_path = PROJECT_DIR / "cycle_state.json"
        if not state_path.exists():
            return {"items": []}
        state = _json.loads(state_path.read_text(encoding="utf-8"))
        deployed = state.get("deployed", []) or []
        items = []
        for item in deployed[-limit:]:
            if isinstance(item, dict):
                items.append({
                    "name": item.get("product", {}).get("name") or item.get("name", ""),
                    "niche": item.get("niche", ""),
                    "url": item.get("url", ""),
                    "verdict": item.get("product", {}).get("verdict") or item.get("verdict", {}),
                })
        return {"items": items}
    except Exception as e:
        logger.warning("content/recent failed: %s", e)
        return {"items": [], "error": str(e)}


# ── n8n integration ────────────────────────────────────────────────
@app.get("/api/n8n/status")
async def n8n_status():
    """n8n reachability for the dashboard and manual checks."""
    from abvorn.core.n8n_bridge import _healthz

    return _healthz()


@app.post("/api/n8n/trigger/{webhook_path}")
async def trigger_n8n(webhook_path: str, data: dict = None):
    """POST to an n8n workflow webhook by path (e.g. abvorn-reflection)."""
    from abvorn.core.n8n_bridge import get_n8n_bridge

    bridge = get_n8n_bridge()
    return bridge.trigger_workflow(webhook_path, data or {})


# ── MoneyPrinterTurbo video render ─────────────────────────────────
@app.get("/api/video/render/health")
async def video_render_health():
    """MPT reachability for the dashboard."""
    from abvorn.core.video_render import get_video_renderer

    return get_video_renderer().health()


@app.post("/api/video/render")
async def video_render(data: dict = None):
    """Submit a script/carousel to MoneyPrinterTurbo and wait for the video.

    Body: any source accepted by build_video_payload (Colosseum carousel,
    domination script, or a raw TaskVideoRequest). Returns the task_id and
    the finished video URLs, or an error dict when MPT is unreachable.
    """
    from abvorn.core.video_render import get_video_renderer

    return get_video_renderer().render(data or {})


@app.get("/api/video/render/tasks/{task_id}")
async def video_render_task(task_id: str):
    """Query MPT task status by task_id."""
    from abvorn.core.video_render import get_video_renderer

    return get_video_renderer().status(task_id)


@app.post("/webhook/abvorn/{action}")
async def abvorn_webhook(action: str, request: Request):
    """Webhook endpoint for n8n to trigger Abvorn actions.

    Actions: generate_reflection, publish_content, gsc_fetch,
    evolution_check, journal_update.

    Authenticated: requires a Bearer token in the Authorization header
    matching ABVORN_API_TOKEN or ABVORN_WEBHOOK_TOKEN. Fail-closed — if no
    token is configured the webhook rejects all requests rather than opening
    an unauthenticated write/publish surface.
    """
    # Authenticate the webhook. Fail closed even when no token is configured.
    webhook_token = (
        os.environ.get("ABVORN_WEBHOOK_TOKEN", "")
        or secrets.get("ABVORN_WEBHOOK_TOKEN", "")
        or _API_TOKEN
    )
    auth = request.headers.get("Authorization", "")
    supplied = auth[len("Bearer "):] if auth.startswith("Bearer ") else ""
    if not webhook_token or not hmac.compare_digest(supplied, webhook_token):
        logger.warning("Rejected unauthenticated webhook action: %s", action)
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        data = await request.json()
    except Exception:
        data = {}
    logger.info("n8n webhook: %s", action)

    if action == "generate_reflection":
        from abvorn.core.learner import HindsightLearner

        learner = HindsightLearner()
        reflection = learner.generate_reflection(
            data.get("content", {}), data.get("performance", {})
        )
        return {"success": True, "reflection_id": reflection.id if reflection else None}

    if action == "publish_content":
        from abvorn.core.colosseum import get_colosseum

        colosseum = get_colosseum()
        result = colosseum.conduct_debate(
            data.get("carousel", {}), data.get("platform", "tiktok")
        )
        return {"success": True, "result": result}

    if action == "gsc_fetch":
        from abvorn.core.gsc_client import GSCClient

        client = GSCClient()
        if not client.enabled:
            return {"success": False, "error": "GSC Client disabled"}
        summary = client.get_summary()
        return {"success": True, **summary}

    if action == "evolution_check":
        from abvorn.core.genesis_protocol import GenesisProtocol

        genesis = GenesisProtocol()
        lineage = genesis.get_lineage()
        generations = lineage.get("generations", [])
        if not isinstance(generations, (list, tuple)):
            generations = [generations] if generations else []

        # A meaningful evolve signal: the v1 core is ready to hand off once it
        # has actually done real work (recorded actions/cycles) since boot.
        # Using `len(generations) > 0` alone was circular (true only *after* an
        # evolution had already happened, so it never triggered the first).
        activities = 0
        activity_path = PROJECT_DIR / "data" / "relentless_state.json"
        try:
            if activity_path.exists():
                import json as _json

                state = _json.loads(activity_path.read_text(encoding="utf-8"))
                activities = len(state.get("history", state.get("outcomes", [])) or [])
        except Exception:
            pass

        return {
            "success": True,
            "lineage": lineage,
            "activities": activities,
            "should_evolve": bool(activities > 0),
        }

    if action == "trigger_evolution":
        from abvorn.core.genesis_protocol import GenesisProtocol

        genesis = GenesisProtocol()
        from_version = genesis.version
        # Safe handoff: record the vN -> vN+1 lineage and write the child
        # genome, but DO NOT terminate the running mobile-server orchestrator
        # (it is the API/loop host, not the core being replaced). The child
        # start.sh is written and can be run/verified without killing live ops.
        # Target is a writable sibling under the project dir (not /opt root,
        # which the ubuntu user cannot create in).
        evo_dir = PROJECT_DIR / "evolutions"
        evo_dir.mkdir(parents=True, exist_ok=True)
        child_path = genesis.transfer_genome(
            target_path=str(evo_dir / f"abvorn_v{genesis.version + 1}")
        )
        lineage = genesis.get_lineage()
        return {
            "success": True,
            "status": "evolved",
            "from_version": from_version,
            "to_version": genesis.version + 1,
            "child_path": child_path,
            "lineage": lineage,
        }

    if action == "journal_update":
        from abvorn.core.cortex_watcher import get_vault_path

        vault = get_vault_path()
        if vault is None:
            return {"success": False, "error": "Cortex vault not configured"}
        journal_dir = vault / "Journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal_file = journal_dir / "n8n-summary.md"
        entry = {
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }
        with open(journal_file, "a", encoding="utf-8") as f:
            f.write(f"{json.dumps(entry, ensure_ascii=False)}\n")
        return {"success": True, "journal": str(journal_file)}

    if action == "render_video":
        from abvorn.core.video_render import VideoRenderer

        renderer = VideoRenderer()
        result = renderer.submit(data.get("video", {}))
        return {"success": result["success"], **result}

    return {"success": False, "error": f"Unknown action: {action}"}


def _call_ai_subprocess(prompt: str) -> str:
    """Call AI in a subprocess with hard timeout. Kills if hung.

    The prompt and system prompt are passed to the child via environment
    variables, never interpolated into the script source, so untrusted user
    input cannot inject Python code (prior versions built a -c script with
    naive quote escaping that was bypassable).
    """
    import subprocess as sp, sys
    script = (
        "import json, os, sys\n"
        "sys.path.insert(0, os.environ['ABVORN_PROJECT_DIR'])\n"
        "from abvorn.core.secrets import load_secrets\n"
        "from abvorn.core.models import ModelRouter\n"
        "s = load_secrets()\n"
        "r = ModelRouter(s, timeout=20)\n"
        "resp = r.ask(os.environ['ABVORN_AI_PROMPT'], system=os.environ['ABVORN_AI_SYSTEM'])\n"
        "print(json.dumps({'response': resp or ''}))\n"
    )
    env = {
        **os.environ,
        "ABVORN_PROJECT_DIR": PROJECT_DIR.as_posix(),
        "ABVORN_AI_PROMPT": prompt,
        "ABVORN_AI_SYSTEM": SYSTEM_PROMPT,
    }
    try:
        p = sp.run([sys.executable, "-c", script], capture_output=True, text=True,
                    timeout=90, cwd=str(PROJECT_DIR), env=env)
        if p.returncode == 0 and p.stdout:
            data = json.loads(p.stdout.strip())
            return data.get("response", "")
        logger.warning(f"AI subprocess failed: {p.stderr[:200]}")
        return ""
    except sp.TimeoutExpired:
        logger.warning("AI subprocess timed out (>90s)")
        return ""
    except Exception as e:
        logger.warning(f"AI subprocess error: {e}")
        return ""


@app.post("/api/chat")
async def chat(msg: ChatMessage):
    chat_history.append({"role": "user", "content": msg.message, "timestamp": datetime.now().isoformat()})
    logger.info(f"Chat request: {msg.message[:50]}")
    response_text = _call_ai_subprocess(msg.message)
    if not response_text:
        response_text = "All AI providers unavailable or timed out. Check network/firewall — DeepSeek, Qwen, and GLM should work from China."
    chat_history.append({"role": "assistant", "content": response_text, "timestamp": datetime.now().isoformat()})
    while len(chat_history) > 200:
        chat_history.pop(0)
    try:
        HISTORY_FILE.write_text(json.dumps(chat_history, indent=2, ensure_ascii=False))
    except Exception:
        pass
    return {"response": response_text, "history_count": len(chat_history)}


@app.post("/api/exec")
async def execute(cmd: CommandRequest):
    cwd = cmd.cwd or str(PROJECT_DIR)
    safe_path = Path(cwd).resolve()
    if not str(safe_path).startswith(str(PROJECT_DIR)):
        return JSONResponse({"error": "Command path outside project directory"}, status_code=403)
    dangerous = ["rm -rf", "rm -fr", "rm -r", "format", "del /f", "rd /s", "rd /q",
                 "shutdown", "restart-computer", "stop-computer", "remove-item",
                 "delete-item", "cleartext", "format-volume", "new-item", "set-content",
                 "add-content", "out-file", "copy-item", "move-item", "ren ", "del ",
                 "remove-", "ii ", "iwr", "invoke-webrequest", "convertto", "bypass",
                 "net user", "net localgroup", "schtasks", "reg add", "sc config"]
    dangerous_re = re.compile("|".join(re.escape(d) for d in dangerous), re.IGNORECASE)
    if dangerous_re.search(cmd.command):
        return JSONResponse({"error": "Dangerous command blocked"}, status_code=403)
    try:
        result = subprocess.run(
            cmd.command, shell=True, capture_output=True, text=True,
            cwd=str(safe_path), timeout=120,
        )
        output = result.stdout or ""
        if result.stderr:
            output += "\n--- STDERR ---\n" + result.stderr
        if result.returncode != 0:
            output += f"\n--- EXIT CODE: {result.returncode} ---"
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode, "output": output}
    except subprocess.TimeoutExpired:
        return JSONResponse({"error": "Command timed out after 120s"}, status_code=408)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/read")
async def read_file(req: FileRequest):
    path = Path(req.path)
    if not path.is_absolute():
        path = PROJECT_DIR / path
    path = path.resolve()
    if not str(path).startswith(str(PROJECT_DIR)):
        return JSONResponse({"error": "Path outside project directory"}, status_code=403)
    if not path.exists():
        return JSONResponse({"error": "Path not found"}, status_code=404)
    if path.is_dir():
        items = []
        for entry in sorted(path.iterdir()):
            items.append({
                "name": entry.name,
                "is_dir": entry.is_dir(),
                "size": entry.stat().st_size if entry.is_file() else 0,
                "modified": datetime.fromtimestamp(entry.stat().st_mtime).isoformat(),
            })
        return {"type": "directory", "path": str(path), "items": items}
    try:
        content = path.read_text(encoding="utf-8")
        return {"type": "file", "path": str(path), "content": content, "size": path.stat().st_size}
    except Exception as e:
        return JSONResponse({"error": f"Cannot read file: {e}"}, status_code=500)


@app.post("/api/write")
async def write_file(req: FileRequest):
    path = Path(req.path)
    if not path.is_absolute():
        path = PROJECT_DIR / path
    path = path.resolve()
    if not str(path).startswith(str(PROJECT_DIR)):
        return JSONResponse({"error": "Path outside project directory"}, status_code=403)
    if req.content is None:
        return JSONResponse({"error": "No content provided"}, status_code=400)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(req.content, encoding="utf-8")
        return {"status": "ok", "path": str(path), "size": len(req.content)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/history")
async def get_history(limit: int = 50):
    return {"history": chat_history[-limit:]}


@app.post("/api/history/clear")
async def clear_history():
    chat_history.clear()
    try:
        HISTORY_FILE.write_text("[]")
    except Exception:
        pass
    return {"status": "ok"}


class PriceAlertRequest(BaseModel):
    email: Optional[str] = None
    chat_id: Optional[str] = None
    asin: str
    target_price: float
    current_price: Optional[float] = None


@app.post("/api/price-alerts")
async def create_price_alert(req: PriceAlertRequest):
    try:
        from src.price_alerts import PriceAlertSystem
        system = PriceAlertSystem()
        ok = system.add_alert(
            asin=req.asin,
            target_price=req.target_price,
            current_price=req.current_price,
            email=req.email,
            chat_id=req.chat_id,
        )
        if not ok:
            raise HTTPException(status_code=400, detail="Invalid alert payload")
        return {"status": "ok", "message": "Alert saved"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/price-alerts")
async def list_price_alerts(email: Optional[str] = None, chat_id: Optional[str] = None):
    try:
        from src.price_alerts import PriceAlertSystem
        system = PriceAlertSystem()
        items = system.get_alerts_for_user(email=email, chat_id=chat_id)
        return {"alerts": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SubscribeRequest(BaseModel):
    email: str
    name: Optional[str] = ""
    list_name: Optional[str] = "Abvorn Subscribers"


@app.post("/api/newsletter/subscribe")
async def newsletter_subscribe(req: SubscribeRequest):
    try:
        from src.listmonk_client import get_listmonk
        listmonk = get_listmonk()
        list_id = listmonk.get_or_create_list(req.list_name or "Abvorn Subscribers")
        if not list_id:
            raise HTTPException(status_code=503, detail="Listmonk unavailable")
        sub = listmonk.create_subscriber(req.email, req.name or "", [list_id])
        if not sub:
            raise HTTPException(status_code=400, detail="Subscribe failed")
        return {"status": "ok", "list_id": list_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/newsletter/lists")
async def newsletter_lists():
    try:
        from src.listmonk_client import get_listmonk
        listmonk = get_listmonk()
        return {"lists": listmonk.get_lists()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/entitlements/pending")
async def entitlements_pending():
    """List actions awaiting operator approval."""
    try:
        from abvorn.core.entitlements import get_entitlements
        return {"pending": get_entitlements().get_pending()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/entitlements/approve")
async def entitlements_approve(index: int = 0):
    """Approve a pending action by index."""
    try:
        from abvorn.core.entitlements import get_entitlements
        ok = get_entitlements().approve(index)
        if not ok:
            raise HTTPException(status_code=400, detail="Invalid pending index")
        return {"status": "ok", "approved": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/entitlements/deny")
async def entitlements_deny(index: int = 0):
    """Deny a pending action by index."""
    try:
        from abvorn.core.entitlements import get_entitlements
        ok = get_entitlements().deny(index)
        if not ok:
            raise HTTPException(status_code=400, detail="Invalid pending index")
        return {"status": "ok", "denied": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/entitlements/audit")
async def entitlements_audit(limit: int = 20):
    """Get recent approval/denial history."""
    try:
        from abvorn.core.entitlements import get_entitlements
        return {"audit": get_entitlements().get_audit_log(limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/surplus")
async def surplus_metrics():
    """Measure whether reflections correlate with better content performance."""
    try:
        from abvorn.core.reflection import ReflectionStore
        store = ReflectionStore()
        return store.get_surplus_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    port = int(os.getenv("ABVORN_SERVER_PORT", "8080"))
    print(f"\n  Abvorn Mobile Server running!")
    print(f"  Local:   http://localhost:{port}")
    print(f"  Network: http://{local_ip}:{port}")
    print(f"  Open on your phone browser to access the PWA.\n")
    if _API_TOKEN:
        print(f"  Auth:    Bearer {_API_TOKEN} (set ABVORN_API_TOKEN in env or secrets)")
    else:
        print("  Auth:    DISABLED — set ABVORN_API_TOKEN in secrets.json to protect /api/*")
    print()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
