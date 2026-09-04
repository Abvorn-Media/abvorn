### CELL 3
# -*- coding: utf-8 -*-
"""Abvorn v13 — Cell 3: Deployer & Evolution (CEO Control Panel + Site Builder)"""
!pip -q install --upgrade PyGithub composio-core

import json, re, requests, time, shutil, logging
from datetime import datetime
from pathlib import Path
from html import escape as html_escape
from github import Github, Auth, InputGitTreeElement
from composio import ComposioToolSet, Action

# ── SELF-SUFFICIENT SECRETS (works standalone or after Cell 1) ──
try:
    _s = S  # from Cell 1 if running sequentially
except NameError:
    _s = None
if _s:
    S = _s
else:
    from abvorn.core.secrets import load_secrets
    S = load_secrets()

GITHUB_TOKEN = S["GITHUB_TOKEN"]
GITHUB_REPO = S["GITHUB_REPO"]
SITE_URL = S["SITE_URL"]
LOGO_URL = f"{SITE_URL}/logo.svg"
COMPOSIO_KEY = S["COMPOSIO_KEY"]
GA4_MEASUREMENT_ID = S["GA4_MEASUREMENT_ID"]
GA4_PROPERTY_ID = S.get("GA4_PROPERTY_ID", "")
_ga4_creds = S.get("GA4_CREDENTIALS_JSON", "")
_ga4_creds_file = BOARDROOM_DIR / "ga4_credentials.json"
if not _ga4_creds and _ga4_creds_file.exists():
    _ga4_creds = _ga4_creds_file.read_text().strip()
GA4_CREDENTIALS_JSON = _ga4_creds
CONTACT_EMAIL = "abvorn.hq@gmail.com"
TELEGRAM_TOKEN = S.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = S.get("TELEGRAM_CHAT_ID", "")

# Standalone fallback paths (overridden by Cell 1 globals when sequential)
try:
    _boardroom = BOARDROOM_DIR
except NameError:
    _boardroom = Path('/content/drive/MyDrive/The_Synthetic_Boardroom')
BOARDROOM_DIR = _boardroom
EMPIRE_DIR = BOARDROOM_DIR / "6_Empire_Network"
SKILLS_DIR = BOARDROOM_DIR / "Design_Skills"
STATE_FILE = BOARDROOM_DIR / "empire_state.json"
# Unified base-path helper (matches Cell 1). Deriving the base path from the
# path component of SITE_URL keeps root-domain deploys (custom CNAME / org
# Pages, e.g. https://abvorn.com) root-relative (SITE_BASE_PATH="") and any
# GitHub Pages subpath deploy (https://owner.github.io/repo) on "/repo".
def _compute_site_base_path(site_url):
    from urllib.parse import urlparse

    if not site_url:
        return ""
    return urlparse(site_url).path.rstrip("/")

SITE_BASE_PATH = _compute_site_base_path(S["SITE_URL"])

# Logger fallback
try:
    _logger = logger
except NameError:
    _logger = logging.getLogger("abvorn_cell3")
    if not _logger.handlers:
        _logger.addHandler(logging.StreamHandler())
        _logger.setLevel(logging.INFO)
logger = _logger

# Lazy import for GA4 Data API
_ga4_client = None
def get_ga4_client():
    global _ga4_client
    if _ga4_client is not None:
        return _ga4_client
    if not GA4_PROPERTY_ID or not GA4_CREDENTIALS_JSON:
        return None
    try:
        import google.analytics.data_v1beta as ga4
        from google.oauth2 import service_account
        import json as _json
        creds = service_account.Credentials.from_service_account_info(_json.loads(GA4_CREDENTIALS_JSON))
        _ga4_client = ga4.BetaAnalyticsDataClient(credentials=creds)
        return _ga4_client
    except Exception as e:
        print(f"   GA4 client init failed: {e} (set GA4_PROPERTY_ID and GA4_CREDENTIALS_JSON in secrets)")
        return None

def pull_ga4_analytics():
    """Pull real page views, active users, and duration from GA4 via abvorn."""
    from abvorn.deploy.analytics import pull_ga4_analytics as _pull_ga4
    result = _pull_ga4(S)
    if not result:
        print("   GA4: credentials not configured")
        print("   ── GA4 Setup Guide ──")
        print("   1. Go to https://console.cloud.google.com/ → create project (or use existing)")
        print("   2. Enable the Analytics Data API (google.analytics.data_v1beta)")
        print("   3. Create a service account under IAM & Admin → Service Accounts")
        print("   4. Generate a JSON key → save as GA4_CREDENTIALS_JSON in secrets")
        print("   5. In Google Analytics → Admin → Property Access Management → add service account email as Viewer")
        print("   6. Find your Property ID in GA4 → Admin → Property Settings → Property ID → set as GA4_PROPERTY_ID")
        print("   ──────────────────────")
    else:
        print(f"   GA4: pulled analytics for {len(result)} niches")
    return result

g = Github(auth=Auth.Token(GITHUB_TOKEN)) if GITHUB_TOKEN else None
repo = g.get_repo(GITHUB_REPO) if g else None
composio = None
try: composio = ComposioToolSet(api_key=COMPOSIO_KEY)
except: print(f"Composio not available")

# ── CROSS-CELL FUNCTION STUBS (for standalone mode) ──
try:
    _notify = notify
except NameError:
    def notify(msg, parse_mode="Markdown", _retry=0):
        if not TELEGRAM_TOKEN or "YOUR_TELEGRAM" in TELEGRAM_TOKEN: return False
        if not TELEGRAM_CHAT_ID or "YOUR_" in str(TELEGRAM_CHAT_ID): return False
        chat_id = str(TELEGRAM_CHAT_ID).strip().lstrip('-').lstrip('0')
        payload = {"chat_id": chat_id, "text": str(msg), "disable_web_page_preview": True}
        if parse_mode not in (None, "None", ""): payload["parse_mode"] = parse_mode
        try:
            r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json=payload, timeout=15)
            return r.status_code == 200
        except: return False
notify = _notify

try:
    _ask_ai = ask_ai
except NameError:
    def ask_ai(prompt, json_mode=False, use_soul=True, model_priority=('glm','deepseek','openai')):
        logger.warning("ask_ai not available (Cell 1 not loaded)")
        return None
ask_ai = _ask_ai

try:
    _load_state = load_state
except NameError:
    def load_state(): return {}
load_state = _load_state

try:
    _save_state = save_state
except NameError:
    def save_state(s): pass
save_state = _save_state

try:
    _captain_query = captain_query
except NameError:
    def captain_query(g, p, q): return None, "stub"
captain_query = _captain_query

try:
    _captain_execute = captain_execute
except NameError:
    def captain_execute(g, p, a, params=None): return None
captain_execute = _captain_execute

try:
    _resolve_prediction = resolve_prediction
except NameError:
    def resolve_prediction(n, a, t=0): pass
resolve_prediction = _resolve_prediction

try:
    _design_enterprise = design_enterprise_structure
except NameError:
    def design_enterprise_structure(s): return {}
design_enterprise_structure = _design_enterprise

try:
    _spawn_general = spawn_general_if_needed
except NameError:
    def spawn_general_if_needed(s): return None
spawn_general_if_needed = _spawn_general

try:
    _evaluate_captain = evaluate_captain
except NameError:
    def evaluate_captain(g, p): return None
evaluate_captain = _evaluate_captain

try:
    _track_persona = track_persona_outcome
except NameError:
    def track_persona_outcome(pid, quality_score=0, views=0, users=0): return None
track_persona_outcome = _track_persona

# ── CEO COMMAND POLLING ─────────────────────────────────────────────────────
_last_command_offset = 0

def poll_ceo_commands():
    global _last_command_offset
    if not TELEGRAM_TOKEN or "YOUR_TELEGRAM" in TELEGRAM_TOKEN: return
    try:
        resp = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates", params={"offset": _last_command_offset, "timeout": 5}, timeout=10)
        if resp.status_code != 200: return
        data = resp.json()
        if not data.get("ok") or not data.get("result"): return
    except: return
    state = load_state()
    for update in data["result"]:
        update_id = update.get("update_id", 0)
        _last_command_offset = max(_last_command_offset, update_id + 1)
        msg = update.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if chat_id != str(TELEGRAM_CHAT_ID).strip(): continue
        text = (msg.get("text") or "").strip()
        if not text.startswith("/"): continue
        command = text.split()[0].lower()
        args = text[len(command):].strip()
        reply = None
        if command == "/help":
             reply = """CEO Commands:
/status — Empire status
/deploy — Force deploy now
/add <niche> — Add niche to queue
/pause — Pause processing
/resume — Resume processing
/niches — List all niches
/queue — Show processing queue
/predict — AI performance prediction
/report — Generate report
/enterprise — Show organizational structure
/generals — List active Generals
/rss — Regenerate RSS feed
/social — Post social media for last 5 niches
/predictions — Show prediction accuracy
/captains — Show General & Captain hierarchy
/help — This message"""
        elif command == "/status":
            reply = f"Empire Status:\nDeployed: {len(state.get('deployed',[]))}\nCompleted: {len(state.get('completed',[]))}\nFailed: {len(state.get('failed',[]))}\nQueue: {len(state.get('queue',[]))}\nGenerals: {len(state.get('generals',{}))}"
        elif command == "/deploy":
            reply = "Deploy triggered."
        elif command == "/add" and args:
            slug = args.replace(" ", "_").lower()
            if slug not in [q['slug'] for q in state['queue']] and slug not in state.get('deployed',[]) and slug not in state.get('completed',[]):
                state['queue'].append({"slug": slug, "niche": args, "stage": "products"})
                save_state(state)
                reply = f"Added '{args}' to queue."
            else: reply = f"'{args}' already in queue or deployed."
        elif command == "/pause": state['paused'] = True; save_state(state); reply = "System paused."
        elif command == "/resume": state['paused'] = False; save_state(state); reply = "System resumed."
        elif command == "/niches":
            all_n = set(state.get('deployed',[]) + state.get('completed',[]) + [q['slug'] for q in state.get('queue',[])])
            reply = "Niches:\n" + "\n".join(f"- {n}" for n in sorted(all_n)) if all_n else "No niches yet."
        elif command == "/queue":
            q = state.get('queue',[])
            reply = "Queue:\n" + "\n".join(f"- {item['slug']} ({item.get('stage','pending')})" for item in q) if q else "Queue is empty."
        elif command == "/predict":
            prompt = f"Based on current state: deployed={len(state.get('deployed',[]))}, queue={len(state.get('queue',[]))}, failed={len(state.get('failed',[]))}, performances={json.dumps({k:v.get('conversions',0) if isinstance(v,dict) else 0 for k,v in state.get('performance',{}).items()})}. Predict next 30 days in one paragraph."
            reply = ask_ai(prompt, use_soul=True) or "Prediction unavailable."
        elif command == "/report":
            lines = ["Executive Report", datetime.now().strftime("%Y-%m-%d %H:%M"),"",f"Deployed: {len(state.get('deployed',[]))}",f"Completed: {len(state.get('completed',[]))}",f"Failed: {len(state.get('failed',[]))}",f"Queue: {len(state.get('queue',[]))}",f"Generals: {len(state.get('generals',{}))}",f"Email subs: {len(state.get('email_schedule',[]))}"]
            reply = "\n".join(lines)
        elif command == "/enterprise":
            struct = state.get('enterprise_structure', {})
            if struct:
                s = struct.get('structure', {})
                lines = ["Enterprise Structure:", f"Phase: {s.get('name','N/A')}", f"Division: {s.get('division','N/A')}"]
                for role in s.get('roles',[]): lines.append(f"  - {role.get('title','Role')}: {role.get('general_name','none')}")
                gaps = struct.get('gaps_detected',[])
                if gaps: lines.append("Gaps: " + ", ".join(gaps))
                reply = "\n".join(lines)
            else: reply = "No enterprise structure yet."
        elif command == "/generals":
            gens = state.get('generals',{})
            if gens:
                lines = ["Active Generals:"]
                for name, gen in gens.items():
                    lines.append(f"- {gen.get('name',name)} ({gen.get('status','unknown')}) domain: {gen.get('domain','?')}, cycles: {gen.get('performance',{}).get('cycles_active',0)}")
                reply = "\n".join(lines)
            else: reply = "No Generals active."
        elif command == "/rss":
            build_rss_feed(load_state())
            reply = "RSS feed regenerated."
        elif command == "/social":
            state = load_state()
            posted = 0
            for slug in state.get('deployed', [])[-5:]:
                try:
                    publish_social_media(slug, slug.replace('_', ' ').title())
                    posted += 1
                except: pass
            reply = f"Social posted for {posted} niche(s)."
        elif command == "/predictions":
            state = load_state()
            acc = state.get('prediction_accuracy', {})
            total = acc.get('total', 0)
            correct = acc.get('correct', 0)
            rate = (correct / total * 100) if total else 0
            lines = [f"Prediction Accuracy: {rate:.0f}% ({correct}/{total})"]
            for name, pred in list(state.get('predictions', {}).items())[-5:]:
                status = "✓" if pred.get('resolved') else "○"
                exp = pred.get('expected_conversions', '?')
                act = pred.get('actual_conversions', '?')
                lines.append(f"  {status} {name}: expected {exp}, actual {act}")
            reply = "\n".join(lines)
        elif command == "/captains":
            state = load_state()
            generals = state.get('generals', {})
            lines = ["General & Captain Status:"]
            for gname, gen in generals.items():
                lines.append(f"  {gen.get('name', gname)} ({gen.get('status', '?')})")
                for pname, cap in gen.get('captains', {}).items():
                    perf = cap.get('performance', {})
                    q_ans = cap.get('queries_answered', 0)
                    q_esc = cap.get('queries_escalated', 0)
                    lines.append(f"    └ {cap.get('name', pname)}: {perf.get('posts',0)} posts, queries {q_ans}/{q_esc}, eval: {cap.get('last_evaluation', 'none')}")
            reply = "\n".join(lines) if len(lines) > 1 else "No Captains active yet."
        if reply: notify(reply, parse_mode="Markdown")

# ── HOMEPAGE ───────────────────────────────────────────────────────────────
HOMEPAGE_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/svg+xml" href="__SITE_BASE_PATH__/favicon.svg">
    <title>Abvorn – The Fortress of Knowledge</title>
    <meta name="description" content="Expert-curated product reviews and buying guides. Independent, honest, rigorously researched.">
    <meta property="og:title" content="Abvorn – The Fortress of Knowledge">
    <meta property="og:description" content="Expert-curated product reviews and buying guides.">
    <meta property="og:image" content="__SITE_BASE_PATH__/logo.svg">
    <meta name="twitter:card" content="summary_large_image">
    <link rel="alternate" type="application/rss+xml" title="Abvorn RSS Feed" href="__SITE_BASE_PATH__/rss.xml">
    <link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@600;700;800&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <script type="application/ld+json">{"@context":"https://schema.org","@type":"WebSite","name":"Abvorn","url":"__SITE_URL__","potentialAction":{"@type":"SearchAction","target":"__SITE_URL__/search?q={search_term_string}","query-input":"required name=search_term_string"}}</script>
    <style>
:root{--clr-primary:#1a1a1a;--clr-secondary:#c98a2c;--clr-accent:#b4b4b4;--clr-neutral:#d9d9d9;--clr-white:#ffffff;--clr-orange:#f8aa25;--clr-black:#000000;--clr-mid-gray:#888;--radius:12px;--radius-lg:16px}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',sans-serif;background:var(--clr-white);color:#333;line-height:1.6}
/* ── top bar ── */
.top-bar{background:var(--clr-black);color:var(--clr-mid-gray);font-size:0.8rem;padding:6px 0}
.top-bar .container{display:flex;justify-content:space-between;max-width:1200px;margin:0 auto;padding:0 24px}
/* ── header + nav ── */
header{background:var(--clr-black);border-bottom:4px solid var(--clr-primary);padding:12px 0;position:sticky;top:0;z-index:1000}
.navbar{display:flex;justify-content:space-between;align-items:center;max-width:1200px;margin:0 auto;padding:0 24px}
    .logo-link{display:flex;align-items:center;gap:10px;text-decoration:none}
    .footer-logo{max-height:24px;width:auto;filter:brightness(0.8);margin-bottom:8px}

.logo-img{max-height:36px;width:auto}
.nav-links{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.nav-links>a,.nav-links>.drop-trigger{color:var(--clr-white);text-decoration:none;font-weight:500;font-size:0.9rem;cursor:pointer;padding:4px 0;transition:opacity 0.2s}
.nav-links>a:hover,.nav-links>.drop-trigger:hover{opacity:0.8}
.nav-links .social-icon{display:inline-flex;width:18px;height:18px;opacity:0.7;transition:opacity 0.2s}
.nav-links .social-icon:hover{opacity:1}
/* niche dropdown */
.drop-trigger{position:relative}
.dropdown{display:none;position:absolute;top:100%;left:-12px;background:#1a1a2e;border:1px solid #333;border-radius:var(--radius);padding:12px 0;min-width:480px;max-width:600px;z-index:999;box-shadow:0 16px 48px rgba(0,0,0,0.4);grid-template-columns:1fr 1fr;gap:4px}
.dropdown.show{display:grid}
.dropdown-cat{padding:4px 16px;grid-column:1/-1}
.dropdown-cat strong{color:var(--clr-primary);font-size:0.75rem;text-transform:uppercase;letter-spacing:1px}
.dropdown a{display:block;padding:5px 16px;color:#ccc;text-decoration:none;font-size:0.82rem;transition:all 0.15s}
.dropdown a:hover{color:var(--clr-white);background:rgba(255,255,255,0.05)}
/* ── trending posts slider ── */
.trending-section{padding:40px 0 20px;max-width:1200px;margin:0 auto}
.trending-section h2{font-family:'Libre Franklin',-apple-system,sans-serif;font-size:1.8rem;margin-bottom:16px;padding:0 24px;display:flex;align-items:center;gap:8px}
.trending-section h2 span{font-size:1.6rem}
.trending-scroll{display:flex;gap:16px;overflow-x:auto;padding:8px 24px 16px;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;scrollbar-width:thin}
.trending-scroll::-webkit-scrollbar{height:4px}
.trending-scroll::-webkit-scrollbar-thumb{background:var(--clr-accent);border-radius:4px}
.trending-slide{flex:0 0 260px;scroll-snap-align:start;border-radius:var(--radius);overflow:hidden;border:1px solid var(--clr-neutral);transition:transform 0.2s;background:var(--clr-white)}
.trending-slide:hover{transform:translateY(-4px);box-shadow:0 8px 24px rgba(0,0,0,0.08)}
.trending-slide img{width:100%;height:140px;object-fit:cover;display:block}
.trending-slide-body{padding:12px 14px 14px}
.trending-slide-body .badge{font-size:0.7rem;color:var(--clr-primary);font-weight:600;text-transform:uppercase}
.trending-slide-body h3{font-size:0.9rem;margin:4px 0;line-height:1.4}
.trending-slide-body h3 a{color:var(--clr-black);text-decoration:none}
.trending-slide-body h3 a:hover{color:var(--clr-primary)}
/* ── hero ── */
.hero{background:linear-gradient(135deg,var(--clr-black) 0%,#1a1a2e 50%,var(--clr-black) 100%);color:var(--clr-white);text-align:center;padding:80px 24px 60px}
.hero h1{font-family:'Libre Franklin',-apple-system,sans-serif;font-size:3.6rem;margin-bottom:12px;letter-spacing:-0.02em}
.hero h1 span{color:var(--clr-primary)}
.hero p{font-size:1.15rem;opacity:0.8;max-width:620px;margin:0 auto 28px;line-height:1.7}
.hero-cta{background:var(--clr-orange);color:var(--clr-black);padding:14px 44px;text-decoration:none;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;display:inline-block;border-radius:8px;transition:transform 0.2s,box-shadow 0.2s}
.hero-cta:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(248,170,37,0.4)}
.hero-sub{display:flex;justify-content:center;gap:40px;margin-top:32px;flex-wrap:wrap}
.hero-sub-item{text-align:center}
.hero-sub-item .num{font-size:1.8rem;font-weight:700;color:var(--clr-orange)}
.hero-sub-item .lbl{font-size:0.85rem;opacity:0.6}
/* ── ticker (dark bg, white text readable) ── */
.trending-ticker{background:#1a1a2e;color:var(--clr-white);padding:10px 0;font-size:0.85rem;overflow:hidden;white-space:nowrap;border-bottom:1px solid #333}
.trending-ticker__track{display:inline-flex;animation:ticker-scroll 30s linear infinite}
.trending-ticker__label{font-weight:700;margin-right:12px;text-transform:uppercase;letter-spacing:0.5px;color:var(--clr-orange)}
.trending-ticker__inner{display:inline-block}
.trending-ticker__item{color:var(--clr-white);text-decoration:none;padding:0 10px;opacity:0.85}
.trending-ticker__item:hover{opacity:1;text-decoration:underline}
@keyframes ticker-scroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
/* ── category tabs + grid ── */
.section-title{text-align:center;max-width:1200px;margin:48px auto 0;padding:0 24px}
.section-title h2{font-family:'Libre Franklin',-apple-system,sans-serif;font-size:2.2rem;color:var(--clr-black)}
.section-title p{color:var(--clr-mid-gray);margin-top:6px;font-size:0.95rem}
.category-tabs{display:flex;justify-content:center;gap:10px;margin:24px auto;padding:0 24px;flex-wrap:wrap}
.category-tab{padding:6px 18px;border:2px solid var(--clr-accent);border-radius:20px;background:transparent;color:#555;cursor:pointer;font-weight:600;font-size:0.85rem;transition:all 0.2s}
.category-tab:hover{border-color:var(--clr-orange);color:var(--clr-orange)}
.category-tab.active{background:var(--clr-orange);color:var(--clr-white);border-color:var(--clr-orange)}
.niche-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:28px;max-width:1200px;margin:32px auto 60px;padding:0 24px}
.niche-card{border:1px solid var(--clr-neutral);padding:0;border-radius:var(--radius-lg);overflow:hidden;transition:transform 0.3s,box-shadow 0.3s;background:var(--clr-white);display:flex;flex-direction:column}
.niche-card:hover{transform:translateY(-6px);box-shadow:0 16px 40px rgba(0,0,0,0.1)}
.niche-card img{width:100%;height:180px;object-fit:cover;display:block}
.niche-card-body{padding:16px 20px 16px;display:flex;flex-direction:column;flex:1}
.niche-card-body h2{font-family:'Libre Franklin',-apple-system,sans-serif;font-size:1.3rem;margin:0 0 6px}
.niche-card-body h2 a{color:var(--clr-black);text-decoration:none}
.niche-card-body h2 a:hover{color:var(--clr-primary)}
.niche-card-body p{font-size:0.85rem;color:#666;margin-bottom:10px;flex:1;line-height:1.5}
.niche-card-meta{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap}
.niche-card-meta span{font-size:0.75rem;color:var(--clr-mid-gray);display:flex;align-items:center;gap:4px}
.niche-card-meta .badge{background:var(--clr-orange);padding:2px 10px;border-radius:12px;font-size:0.7rem;font-weight:600;color:var(--clr-black)}
.niche-card .card-actions{display:flex;gap:6px;align-items:center;border-top:1px solid var(--clr-neutral);padding:10px 20px}
.card-actions button{background:none;border:1px solid var(--clr-neutral);border-radius:6px;padding:5px 10px;cursor:pointer;font-size:0.8rem;color:#555;transition:all 0.2s;display:flex;align-items:center;gap:4px}
.card-actions button:hover{background:var(--clr-neutral)}
.card-actions button.liked{color:var(--clr-primary);border-color:var(--clr-primary);background:rgba(90,125,154,0.08)}
.card-actions button.loved{color:#e74c3c;border-color:#e74c3c;background:rgba(231,76,60,0.08)}
.card-actions .explore-btn{background:var(--clr-orange);color:var(--clr-black);padding:7px 18px;border-radius:6px;text-decoration:none;font-weight:600;font-size:0.8rem;margin-left:auto;transition:background 0.2s}
.card-actions .explore-btn:hover{background:#e09920}
/* ── footer ── */
.footer{background:var(--clr-black);color:var(--clr-mid-gray);padding:40px 24px;text-align:center}
.footer .footer-socials{display:flex;justify-content:center;gap:16px;margin-bottom:16px}
.footer .footer-socials a{display:inline-flex;width:22px;height:22px;opacity:0.5;transition:opacity 0.2s}
.footer .footer-socials a:hover{opacity:1}
.footer nav{display:flex;justify-content:center;flex-wrap:wrap;gap:14px;margin-bottom:12px}
.footer nav a{color:var(--clr-accent);text-decoration:none;font-size:0.85rem}
.footer nav a:hover{color:var(--clr-white)}
.footer p{font-size:0.8rem}
/* ── responsive ── */
@media(max-width:768px){.hero h1{font-size:2rem}.hero{padding:50px 24px 40px}.hero-sub{gap:20px}.dropdown{min-width:280px;left:0;grid-template-columns:1fr}.trending-slide{flex:0 0 200px}.niche-grid{grid-template-columns:1fr}.section-title h2{font-size:1.6rem}.category-tabs{gap:6px}}}
    </style>
</head>
<body>
<div class="top-bar"><div class="container"><span>Independent product reviews since 2025</span><span><a href="__SITE_BASE_PATH__/rss.xml" style="color:var(--clr-mid-gray);text-decoration:none">RSS Feed</a></span></div></div>
<header><div class="navbar"><a href="__SITE_BASE_PATH__/" class="logo-link"><img src="__SITE_BASE_PATH__/logo.svg" alt="Abvorn" class="logo-img"></a><nav class="nav-links"><a href="__SITE_BASE_PATH__/">Home</a><span class="drop-trigger" onmouseenter="document.getElementById('niche-dropdown').classList.add('show')" onmouseleave="document.getElementById('niche-dropdown').classList.remove('show')">Guides \u25BE<div class="dropdown" id="niche-dropdown">DROPDOWN_ITEMS</div></span><a href="__SITE_BASE_PATH__/about.html">About</a><a href="__SITE_BASE_PATH__/contact.html">Contact</a><a href="https://www.instagram.com/abvorn/" class="social-icon" target="_blank" rel="noopener" aria-label="Instagram"><svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zM12 16c-2.209 0-4-1.79-4-4s1.791-4 4-4 4 1.791 4 4-1.791 4-4 4zM18.406 4.155c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg></a><a href="https://www.tiktok.com/@abvorn" class="social-icon" target="_blank" rel="noopener" aria-label="TikTok"><svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg></a><a href="https://x.com/Abvorn" class="social-icon" target="_blank" rel="noopener" aria-label="X"><svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg></a></nav></div></header>

<!-- Trending Posts Slider (first content section) -->
<section class="trending-section">
    <h2><span>\uD83D\uDD25</span> Trending Now</h2>
    <div class="trending-scroll" id="trending-scroll">TRENDING_POSTS_PLACEHOLDER</div>
</section>

<div class="trending-ticker"><div class="container"><div class="trending-ticker__track"><span class="trending-ticker__label">Trending Now:</span><span id="trending-items" class="trending-ticker__inner">Loading...</span><span id="trending-items-dup" class="trending-ticker__inner" aria-hidden="true">Loading...</span></div></div></div>

<section class="hero">
    <h1>The <span>Fortress</span> of Knowledge</h1>
    <p>Expert-curated product reviews, buying guides, and recommendations \u2014 rigorously researched, independently produced, and built to help you make smarter decisions.</p>
    <a href="#guides" class="hero-cta">Explore Guides</a>
    <div class="hero-sub">
        <div class="hero-sub-item"><div class="num" id="hero-count">0</div><div class="lbl">Expert Guides</div></div>
        <div class="hero-sub-item"><div class="num">100%</div><div class="lbl">Independent</div></div>
        <div class="hero-sub-item"><div class="num" id="hero-products">0</div><div class="lbl">Products Reviewed</div></div>
    </div>
</section>

<div class="section-title" id="guides"><h2>All Guides</h2><p>Browse by category \u2014 find the perfect guide for your needs</p></div>
<div class="category-tabs" id="category-tabs">CATEGORY_TABS_PLACEHOLDER</div>
<section class="niche-grid">NICHE_CARDS_PLACEHOLDER</section>

<footer class="footer">
    <div class="footer-socials">
        <a href="https://www.instagram.com/abvorn/" target="_blank" rel="noopener" aria-label="Instagram"><svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zM12 16c-2.209 0-4-1.79-4-4s1.791-4 4-4 4 1.791 4 4-1.791 4-4 4zM18.406 4.155c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg></a>
        <a href="https://www.tiktok.com/@abvorn" target="_blank" rel="noopener" aria-label="TikTok"><svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg></a>
        <a href="https://x.com/Abvorn" target="_blank" rel="noopener" aria-label="X"><svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg></a>
    </div>
    <nav><a href="__SITE_BASE_PATH__/">Home</a><a href="__SITE_BASE_PATH__/about.html">About</a><a href="__SITE_BASE_PATH__/contact.html">Contact</a><a href="__SITE_BASE_PATH__/rss.xml">RSS Feed</a></nav>
    <p style="margin-top:8px">Contact: <a href="mailto:__CONTACT_EMAIL__" style="color:var(--clr-accent);text-decoration:none">__CONTACT_EMAIL__</a></p>
    <p>&copy; YEAR_PLACEHOLDER Abvorn. All rights reserved.</p>
</footer>
<script>
// Dropdown: click-to-toggle on mobile, hover on desktop
document.addEventListener('DOMContentLoaded',function(){var dd=document.getElementById('niche-dropdown');var t=dd.closest('.drop-trigger');t.addEventListener('click',function(e){e.stopPropagation();dd.classList.toggle('show')});document.addEventListener('click',function(e){if(!t.contains(e.target))dd.classList.remove('show')})});
// Trending ticker
(async function(){try{var r=await fetch('__SITE_BASE_PATH__/trending.json');var d=await r.json();var h=d.map(function(n){return'<a href="__SITE_BASE_PATH__/'+n.slug+'/" class="trending-ticker__item">'+n.name+'</a>'}).join(' \\u00b7 ');document.getElementById('trending-items').innerHTML=h;document.getElementById('trending-items-dup').innerHTML=h;document.getElementById('hero-count').textContent=d.length;var pc=d.reduce(function(s,n){return s+(n.latest?n.latest.length:0)*2+5},0);document.getElementById('hero-products').textContent=Math.max(pc||15,15)}catch(e){var m='Loading guides...';document.getElementById('trending-items').innerHTML=m;document.getElementById('trending-items-dup').innerHTML=m}})();
// Category filter
document.addEventListener('DOMContentLoaded',function(){var tabs=document.querySelectorAll('.category-tab');var cards=document.querySelectorAll('.niche-card');tabs.forEach(function(t){t.addEventListener('click',function(){tabs.forEach(function(x){x.classList.remove('active')});this.classList.add('active');var cat=this.getAttribute('data-cat');cards.forEach(function(c){c.style.display=cat==='all'||c.getAttribute('data-category')===cat?'flex':'none'})})})});
// Like / Love / Share
function toggleReaction(key,btn){var k='abvorn_'+key+'_'+(window.location.pathname.split('/').filter(Boolean).join('_')||'home');var d=JSON.parse(localStorage.getItem(k)||'{"active":false,"count":0}');d.active=!d.active;d.count+=d.active?1:-1;localStorage.setItem(k,JSON.stringify(d));if(d.active){btn.classList.add(key==='like'?'liked':'loved')}else{btn.classList.remove(key==='like'?'liked':'loved')}btn.innerHTML=btn.innerHTML.replace(/\\d+/,d.count)}
function shareNiche(slug){var url='__SITE_URL__/'+slug+'/';if(navigator.share){navigator.share({title:'Abvorn',url:url})}else{navigator.clipboard.writeText(url);alert('Link copied!')}}
</script>
__GA_TRACKING__
</body>
</html>'''

NICHE_CATEGORIES = {
    "wireless_headphones": "Audio", "bluetooth_speaker": "Audio", "soundbar": "Audio",
    "standing_desk": "Office", "office_chair": "Office", "desk_lamp": "Office", "monitor_arm": "Office",
    "coffee_maker": "Kitchen", "air_fryer": "Kitchen", "blender": "Kitchen", "toaster": "Kitchen",
    "yoga_mat": "Fitness", "treadmill": "Fitness", "dumbbells": "Fitness", "resistance_bands": "Fitness",
    "robot_vacuum": "Home", "air_purifier": "Home", "humidifier": "Home", "smart_thermostat": "Home",
    "webcam": "Tech", "mechanical_keyboard": "Tech", "laptop_stand": "Tech", "usb_hub": "Tech",
    "fountain_pen": "Lifestyle", "journal": "Lifestyle", "notebook": "Lifestyle",
    "dog_food": "Pets", "cat_tower": "Pets", "pet_camera": "Pets",
    "pet_carrier": "Pets", "pet_bed": "Pets",
    "washing_machine": "Home", "dryer": "Home",
    "camera": "Photography", "lens": "Photography", "tripod": "Photography", "camera_bag": "Photography",
    "fitness_tracker": "Health", "sleep_aid": "Health",
    "cookware_set": "Food", "knife_set": "Food",
    "luggage": "Travel", "travel_backpack": "Travel", "travel_pillow": "Travel",
    "running_shoes": "Sports", "sports_bra": "Sports",
    "art_supplies": "Art", "easel": "Art", "paint_brush": "Art",
    "baby_monitor": "Parenting", "stroller": "Parenting", "baby_carrier": "Parenting",
    "high_chair": "Parenting", "baby_car_seat": "Parenting", "diaper_bag": "Parenting",
    "bottle_warmer": "Parenting", "baby_bouncer": "Parenting",
    "gaming_headset": "Gaming", "gaming_mouse": "Gaming", "gaming_chair": "Gaming", "gaming_monitor": "Gaming",
    "dash_cam": "Auto", "car_phone_mount": "Auto", "car_jump_starter": "Auto", "car_seat_cover": "Auto",
    "garden_hose": "Garden", "pruning_shears": "Garden", "garden_tools": "Garden", "plant_pots": "Garden", "outdoor_lighting": "Garden",
    "power_tool_set": "DIY", "tool_box": "DIY", "workbench": "DIY", "ladder": "DIY"
}

STATIC_PAGE_STYLES = '''
:root{--clr-primary:#1a1a1a;--clr-secondary:#c98a2c;--clr-accent:#b4b4b4;--clr-neutral:#d9d9d9;--clr-white:#ffffff;--clr-warning:#f8aa25;--clr-black:#000000;--clr-mid-gray:#888}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',sans-serif;background:var(--clr-white);color:#333;line-height:1.7}
header{background:var(--clr-black);padding:16px 0;border-bottom:4px solid var(--clr-primary)}
.header-inner{max-width:1200px;margin:0 auto;padding:0 24px;display:flex;justify-content:space-between;align-items:center}
.header-inner .logo-img{max-height:40px;width:auto}
.header-inner nav{display:flex;align-items:center;gap:20px}
.header-inner nav a{color:var(--clr-white);text-decoration:none;font-weight:600;font-size:0.95rem}
.header-inner .social-icon{display:inline-flex;width:20px;height:20px;opacity:0.8;transition:opacity 0.2s}
.header-inner .social-icon:hover{opacity:1}
main{max-width:800px;margin:0 auto;padding:60px 24px}
main h1{font-family:'Libre Franklin',-apple-system,sans-serif;font-size:2.4rem;margin-bottom:24px;color:var(--clr-black)}
main h2{font-size:1.3rem;margin:24px 0 12px;color:#444}
main p{margin-bottom:16px;color:#555;font-size:1rem}
main a{color:var(--clr-primary)}
.store-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:20px;margin-top:24px}
.store-card{display:block;padding:20px;border:1px solid var(--clr-neutral);border-radius:12px;text-decoration:none;color:inherit;transition:transform 0.2s,box-shadow 0.2s}
.store-card:hover{transform:translateY(-4px);box-shadow:0 8px 24px rgba(0,0,0,0.08)}
.store-card h3{margin:0 0 6px;font-size:1.1rem;color:var(--clr-black)}
.store-card p{font-size:0.85rem;color:var(--clr-mid-gray);margin:0}
footer{background:var(--clr-black);color:var(--clr-mid-gray);padding:40px 24px;text-align:center}
footer .fsocials{display:flex;justify-content:center;gap:16px;margin-bottom:16px}
footer .fsocials a{display:inline-flex;width:22px;height:22px;opacity:0.5;transition:opacity 0.2s}
footer .fsocials a:hover{opacity:1}
footer nav{margin-bottom:12px;display:flex;justify-content:center;flex-wrap:wrap;gap:12px}
footer nav a{color:var(--clr-accent);text-decoration:none;font-size:0.9rem}
footer nav a:hover{color:var(--clr-white)}
footer p{font-size:0.85rem}
@media(max-width:768px){main h1{font-size:1.8rem}}
'''

SOCIAL_ICONS = {
    "instagram": '<svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zM12 16c-2.209 0-4-1.79-4-4s1.791-4 4-4 4 1.791 4 4-1.791 4-4 4zM18.406 4.155c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>',
    "tiktok": '<svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg>',
    "x": '<svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'
}

HEADER_SOCIALS = '<a href="https://www.instagram.com/abvorn/" class="social-icon" target="_blank" rel="noopener" aria-label="Instagram">' + SOCIAL_ICONS["instagram"] + '</a><a href="https://www.tiktok.com/@abvorn" class="social-icon" target="_blank" rel="noopener" aria-label="TikTok">' + SOCIAL_ICONS["tiktok"] + '</a><a href="https://x.com/Abvorn" class="social-icon" target="_blank" rel="noopener" aria-label="X">' + SOCIAL_ICONS["x"] + '</a>'

FOOTER_SOCIALS = '<a href="https://www.instagram.com/abvorn/" target="_blank" rel="noopener" aria-label="Instagram"><svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zM12 16c-2.209 0-4-1.79-4-4s1.791-4 4-4 4 1.791 4 4-1.791 4-4 4zM18.406 4.155c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg></a><a href="https://www.tiktok.com/@abvorn" target="_blank" rel="noopener" aria-label="TikTok"><svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg></a><a href="https://x.com/Abvorn" target="_blank" rel="noopener" aria-label="X"><svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg></a>'

def build_homepage(state):
    print("   Building premium homepage...")
    deployed = state.get('deployed', [])
    for slug in state.get('completed', []):
        if slug not in deployed: deployed.append(slug)

    if not deployed:
        cards = '<div class="niche-card"><div style="padding:60px;text-align:center;background:var(--clr-black);color:var(--clr-white)"><h2 style="font-family:Libre Franklin,-apple-system,sans-serif">Our First Guide is Brewing</h2><p style="opacity:0.7;margin-top:8px">Stay tuned for expert reviews and guides.</p></div></div>'
        trending_html = '<p style="padding:24px;color:var(--clr-mid-gray)">No guides yet. Check back soon!</p>'
        dropdown_items = ''
        cat_tabs = ''
        ga_tracking = ''
    else:
        seen_categories = set()
        all_cards = []
        all_trending = []
        all_dropdown = {}
        for slug in deployed[-30:]:
            if not slug: continue
            category = NICHE_CATEGORIES.get(slug, "Other")
            seen_categories.add(category)
            if category not in all_dropdown: all_dropdown[category] = []
            all_dropdown[category].append(slug)
            niche_folder = EMPIRE_DIR / slug
            meta_file = niche_folder / "posts_meta.json"
            if not meta_file.exists(): continue
            posts_meta = json.loads(meta_file.read_text())
            if not posts_meta: continue
            latest = posts_meta[-1]
            image = latest.get('image', 'https://via.placeholder.com/800x600?text=Abvorn')
            title = html_escape(slug.replace('_', ' ').title())
            link = html_escape(slug)
            desc = html_escape(latest.get('meta_description', '')[:120])
            article_count = len(posts_meta)
            all_cards.append(f'''<div class="niche-card" data-category="{category}"><a href="__SITE_BASE_PATH__/{link}/"><img src="{image}" alt="{title}" loading="lazy" width="800" height="600"></a><div class="niche-card-body"><div class="niche-card-meta"><span class="badge">{category}</span><span>{article_count} article{'' if article_count == 1 else 's'}</span></div><h2><a href="__SITE_BASE_PATH__/{link}/">{title}</a></h2><p>{desc}...</p></div><div class="card-actions"><button onclick="toggleReaction('like',this)" data-slug="{link}">\uD83D\uDC4D <span id="like-count-{link}">0</span></button><button onclick="toggleReaction('love',this)" data-slug="{link}">\u2764\uFE0F <span id="love-count-{link}">0</span></button><button onclick="shareNiche('{link}')">\uD83D\uDD17</button><a href="__SITE_BASE_PATH__/{link}/" class="explore-btn">Explore \u2192</a></div></div>''')
            # Trending slider: gather recent posts from all niches
            for p in reversed(posts_meta[-3:]):
                p_title = html_escape(p.get('title', '')[:60])
                p_image = p.get('image', image)
                p_file = p.get('file', '')
                p_link = f"{slug}/{p_file}" if p_file else slug
                p_slug = slug
                all_trending.append((p.get('date', ''), p_title, p_image, p_link, p_slug))

        cards = "\n".join(all_cards)
        sorted_cats = sorted(seen_categories)
        cat_tabs = '<button class="category-tab active" data-cat="all">All</button>' + "".join(f'<button class="category-tab" data-cat="{c}">{c}</button>' for c in sorted_cats)

        # Trending posts slider (sorted by date, newest first)
        all_trending.sort(key=lambda x: x[0] or '', reverse=True)
        trending_html = ""
        for _, t_title, t_image, t_link, t_slug in all_trending[:20]:
            t_cat = NICHE_CATEGORIES.get(t_slug, "Other")
            trending_html += f'''<div class="trending-slide"><a href="__SITE_BASE_PATH__/{html_escape(t_link)}"><img src="{t_image}" alt="{t_title}" loading="lazy" width="260" height="140" onerror="this.parentElement.innerHTML=this.parentElement.innerHTML.replace('<img','<div style=\\'height:140px;background:#eee;display:flex;align-items:center;justify-content:center;color:#999;font-size:2rem\\'>\uD83D\uDCDD</div>')"></a><div class="trending-slide-body"><span class="badge">{t_cat}</span><h3><a href="__SITE_BASE_PATH__/{html_escape(t_link)}">{t_title}</a></h3></div></div>'''

        # Dropdown menu items (grouped by category)
        dropdown_sections = []
        for cat in sorted(all_dropdown.keys()):
            links = "".join(f'<a href="__SITE_BASE_PATH__/{html_escape(s)}/">{html_escape(s.replace("_"," ").title())}</a>' for s in all_dropdown[cat])
            dropdown_sections.append(f'<div class="dropdown-cat"><strong>{cat}</strong></div>{links}')
        dropdown_items = "".join(dropdown_sections)

    ga_tracking = f'''<!-- Google Analytics --><script async src="https://www.googletagmanager.com/gtag/js?id={GA4_MEASUREMENT_ID}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA4_MEASUREMENT_ID}');</script>''' if GA4_MEASUREMENT_ID else ''

    html = HOMEPAGE_TEMPLATE.replace('NICHE_CARDS_PLACEHOLDER', cards).replace('TRENDING_POSTS_PLACEHOLDER', trending_html).replace('DROPDOWN_ITEMS', dropdown_items).replace('CATEGORY_TABS_PLACEHOLDER', cat_tabs).replace('YEAR_PLACEHOLDER', str(datetime.now().year)).replace('__SITE_BASE_PATH__', SITE_BASE_PATH).replace('__SITE_URL__', SITE_URL).replace('__GA_TRACKING__', ga_tracking).replace('__CONTACT_EMAIL__', CONTACT_EMAIL)
    (EMPIRE_DIR / "index.html").write_text(html, encoding="utf-8")

    # Static pages with consistent styling (NO store page)
    for page_name, title, content in [
        ("about.html", "About Abvorn", "<h2>Our Mission</h2><p>Abvorn is an independent, AI-powered media network that produces expert product reviews and buying guides. Our mission is simple: <strong>help you make smarter buying decisions</strong> through rigorous research and honest recommendations.</p><h2>How We Work</h2><p>Every guide on Abvorn is independently produced with zero publisher or brand influence. Our AI-powered research engine analyzes thousands of data points \u2014 expert reviews, user feedback, technical specifications \u2014 to surface the products that genuinely deliver value. Each recommendation is then reviewed and refined by our editorial framework to ensure accuracy and fairness.</p><h2>Our Values</h2><p><strong>Independence.</strong> We accept no payment or free products from brands for coverage. Our only revenue comes from affiliate commissions when readers choose to purchase through our links \u2014 and this never affects our ratings or placement.</p><p><strong>Transparency.</strong> Every guide clearly marks affiliate links and explains our review methodology. We believe you deserve to know exactly how we operate.</p><p><strong>Expertise.</strong> We combine cutting-edge AI research with editorial best practices, continuously refining our approach to bring you the most relevant, up-to-date product intelligence.</p>"),
        ("contact.html", "Contact Us", "<h2>Get in Touch</h2><p>Have a question, suggestion, or business inquiry? We'd love to hear from you.</p><p>Email: <a href=\"mailto:"+CONTACT_EMAIL+"\"><strong>"+CONTACT_EMAIL+"</strong></a></p><p>We aim to respond within 24-48 hours during business days.</p><h2>Follow Us</h2><p>Stay updated with the latest guides and reviews:<br>Instagram: <a href=\"https://www.instagram.com/abvorn/\" target=\"_blank\">@abvorn</a><br>TikTok: <a href=\"https://www.tiktok.com/@abvorn\" target=\"_blank\">@abvorn</a><br>X: <a href=\"https://x.com/Abvorn\" target=\"_blank\">@Abvorn</a></p>"),
        ("privacy.html", "Privacy Policy", "<h2>Privacy Policy</h2><p><em>Last updated: "+datetime.now().strftime('%B %d, %Y')+"</em></p><h3>Information We Collect</h3><p>We use cookies and similar tracking technologies to analyze traffic, personalize content, and serve targeted advertisements. When you visit our site, we may collect: browser type, device information, pages visited, time spent, and referral URLs.</p><h3>Google AdSense</h3><p>We use Google AdSense to display advertisements. Google uses cookies (including the DoubleClick DART cookie) to serve ads based on your previous visits to our site or other websites. You can opt out of the DART cookie by visiting Google's Ads Settings at <a href=\"https://adssettings.google.com\" target=\"_blank\">adssettings.google.com</a>.</p><p>Third-party vendors, including Google, use cookies to serve ads based on a user's prior visits to this site and other websites. Users may opt out of personalized advertising by visiting <a href=\"https://www.aboutads.info/choices\" target=\"_blank\">AboutAds.info/choices</a> or <a href=\"https://www.youronlinechoices.com\" target=\"_blank\">YourOnlineChoices.com</a> (EU).</p><h3>Affiliate Links</h3><p>Our site contains affiliate links. If you click on an affiliate link and make a purchase, we may earn a commission at no extra cost to you. These links use cookies to track referrals for commission purposes.</p><h3>Email Collection</h3><p>Email addresses collected through our lead magnet forms are used solely to deliver the requested content and occasional updates. You can unsubscribe at any time. We do not sell or share your email with third parties.</p><h3>Data Retention</h3><p>We retain your data only as long as necessary to provide our services. You may request deletion of your data by contacting us.</p><h3>Contact</h3><p>For privacy-related inquiries: <a href=\"mailto:"+CONTACT_EMAIL+"\">"+CONTACT_EMAIL+"</a></p>")
    ]:
        page_path = EMPIRE_DIR / page_name
        full = f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><link rel="icon" type="image/svg+xml" href="{SITE_BASE_PATH}/favicon.svg"><title>{title} | Abvorn</title><meta name="description" content="{html_escape(content[:150].replace('"',''))}"><link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@600;700;800&family=Inter:wght@400;600;700&display=swap" rel="stylesheet"><style>{STATIC_PAGE_STYLES}</style></head><body><header><div class="header-inner"><a href="{SITE_BASE_PATH}/"><img src="{SITE_BASE_PATH}/logo.svg" alt="Abvorn" class="logo-img"></a><nav><a href="{SITE_BASE_PATH}/">Home</a><a href="{SITE_BASE_PATH}/about.html">About</a><a href="{SITE_BASE_PATH}/contact.html">Contact</a><a href="{SITE_BASE_PATH}/privacy.html">Privacy</a>{HEADER_SOCIALS}</nav></div></header><main><h1>{title}</h1>{content}</main><footer><div class="fsocials">{FOOTER_SOCIALS}</div><nav><a href="{SITE_BASE_PATH}/">Home</a><a href="{SITE_BASE_PATH}/about.html">About</a><a href="{SITE_BASE_PATH}/contact.html">Contact</a><a href="{SITE_BASE_PATH}/privacy.html">Privacy</a><a href="{SITE_BASE_PATH}/rss.xml">RSS Feed</a></nav><img src="{SITE_BASE_PATH}/logo.svg" alt="Abvorn" class="footer-logo"><p style="margin-top:8px;font-size:0.8rem">Contact: <a href="mailto:{CONTACT_EMAIL}" style="color:var(--clr-accent);text-decoration:none">{CONTACT_EMAIL}</a></p><p>&copy; {datetime.now().year} Abvorn. All rights reserved.</p></footer></body></html>'''
        page_path.write_text(full, encoding="utf-8")
    return html

# ── RSS FEED ────────────────────────────────────────────────────────────────
def build_rss_feed(state):
    print("   Building RSS feed...")
    all_posts = []
    for slug in state.get('deployed', []):
        if not slug: continue
        folder = EMPIRE_DIR / slug
        meta_file = folder / "posts_meta.json"
        if not meta_file.exists(): continue
        try:
            posts = json.loads(meta_file.read_text())
            for p in posts:
                all_posts.append({"title": p.get("title", ""), "description": p.get("meta_description", ""), "link": f"{SITE_URL}/{slug}/{p.get('file', '')}", "date": p.get("date", datetime.now().strftime("%Y-%m-%d")), "image": p.get("image", ""), "tags": p.get("tags", [])})
        except: pass
    all_posts.sort(key=lambda x: x.get("date", ""), reverse=True)
    items = ""
    for p in all_posts[:50]:
        date_str = p.get("date", "")
        try: rfc_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%a, %d %b %Y %H:%M:%S +0000")
        except: rfc_date = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
        items += f'''<item>
<title>{html_escape(p.get('title', ''))}</title>
<link>{html_escape(p.get('link', ''))}</link>
<description>{html_escape(p.get('description', ''))}</description>
<pubDate>{rfc_date}</pubDate>
<guid>{html_escape(p.get('link', ''))}</guid>
<enclosure url="{html_escape(p.get('image', ''))}" type="image/jpeg"/>
<source url="{SITE_URL}">Abvorn</source>
</item>'''
    rss = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
<title>Abvorn – Expert Product Reviews</title>
<link>{SITE_URL}</link>
<description>AI-powered, expert-curated product reviews and buying guides.</description>
<language>en-us</language>
<lastBuildDate>{datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
<atom:link href="{SITE_URL}/rss.xml" rel="self" type="application/rss+xml"/>
<image><url>{LOGO_URL}</url><title>Abvorn</title><link>{SITE_URL}</link></image>
{items}
</channel>
</rss>'''
    (EMPIRE_DIR / "rss.xml").write_text(rss, encoding="utf-8")
    print(f"   RSS feed with {min(len(all_posts), 50)} posts written.")

# ── SITEMAP ─────────────────────────────────────────────────────────────────
def build_sitemap(state):
    print("   Building sitemap...")
    urls = [f'''<url><loc>{SITE_URL}/</loc><priority>1.0</priority><changefreq>daily</changefreq></url>''']
    for slug in state.get('deployed', []):
        if not slug: continue
        urls.append(f'''<url><loc>{SITE_URL}/{slug}/</loc><priority>0.9</priority><changefreq>weekly</changefreq></url>''')
        folder = EMPIRE_DIR / slug
        meta_file = folder / "posts_meta.json"
        if meta_file.exists():
            try:
                for p in json.loads(meta_file.read_text()):
                    pf = p.get('file', '')
                    if pf:
                        urls.append(f'''<url><loc>{SITE_URL}/{slug}/{pf}</loc><priority>0.8</priority><changefreq>monthly</changefreq></url>''')
            except: pass
        for extra in ['store.html', 'about.html', 'privacy.html']:
            if (folder / extra).exists():
                urls.append(f'''<url><loc>{SITE_URL}/{slug}/{extra}</loc><priority>0.5</priority><changefreq>monthly</changefreq></url>''')
    for page in ['store.html', 'about.html', 'privacy.html', 'rss.xml']:
        if (EMPIRE_DIR / page).exists():
            urls.append(f'''<url><loc>{SITE_URL}/{page}</loc><priority>0.6</priority><changefreq>monthly</changefreq></url>''')
    sitemap = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{"".join(urls)}
</urlset>'''
    (EMPIRE_DIR / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    print(f"   Sitemap with {len(urls)} URLs.")

# ── SEO PRE-DEPLOY AUDIT ───────────────────────────────────────────────────
def seo_audit_pages(slugs):
    """Validate all new pages before deploy. Returns list of issues found."""
    issues = []
    for slug in slugs:
        if not slug: continue
        folder = EMPIRE_DIR / slug
        if not folder.exists(): continue
        for html_file in folder.glob("*.html"):
            try:
                text = html_file.read_text(encoding='utf-8', errors='replace')
                name = f"{slug}/{html_file.name}"
                # Check meta description
                m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']', text, re.IGNORECASE)
                if not m:
                    issues.append(f"{name}: missing meta description")
                else:
                    desc_len = len(m.group(1))
                    if desc_len < 50: issues.append(f"{name}: meta description too short ({desc_len} chars, min 50)")
                    elif desc_len > 165: issues.append(f"{name}: meta description too long ({desc_len} chars, max 165)")
                # Check H1
                h1 = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.IGNORECASE | re.DOTALL)
                if not h1: issues.append(f"{name}: missing H1 heading")
                # Check image alt attributes
                imgs = re.findall(r'<img[^>]+>', text, re.IGNORECASE)
                missing_alt = sum(1 for img in imgs if 'alt=' not in img and 'alt =' not in img)
                if missing_alt and missing_alt > len(imgs) * 0.3:
                    issues.append(f"{name}: {missing_alt}/{len(imgs)} images missing alt text")
                # Check schema presence
                if 'application/ld+json' not in text:
                    issues.append(f"{name}: no schema markup found")
                # Check minimum word count (rough)
                body = re.search(r'<body[^>]*>(.*?)</body>', text, re.IGNORECASE | re.DOTALL)
                if body:
                    words = len(re.findall(r'\b\w+\b', body.group(1)))
                    if words < 300:
                        issues.append(f"{name}: too short ({words} words, min 300)")
            except Exception as e:
                issues.append(f"{slug}/{html_file.name}: audit error ({str(e)[:60]})")
    if issues:
        report = "\n".join(f"  ⚠ {i}" for i in issues)
        print(f"   SEO audit: {len(issues)} issue(s) found\n{report}")
    else:
        print(f"   SEO audit: {len(slugs)} page(s) — all clean")
    return issues

# ── TRENDING TICKER ─────────────────────────────────────────────────────────
def build_trending_json(state):
    items = []
    for slug in state.get('deployed', []):
        if not slug: continue
        meta_file = EMPIRE_DIR / slug / "posts_meta.json"
        if meta_file.exists():
            try:
                posts = json.loads(meta_file.read_text())
                if posts:
                    items.append({"slug": slug, "name": slug.replace('_', ' ').title(), "latest": posts[-1].get('title', '')})
            except: pass
    (EMPIRE_DIR / "trending.json").write_text(json.dumps(items), encoding="utf-8")

# ── LOGO & FAVICON ──────────────────────────────────────────────────────────
LOGO_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="600" zoomAndPan="magnify" viewBox="0 0 450 149.999998" height="200" preserveAspectRatio="xMidYMid meet" version="1.0"><g fill="#ffffff" fill-opacity="1"><g transform="translate(122.966715, 103.249251)"><g><path d="M 18.390625 -46.015625 L 29.171875 -46.015625 L 48.28125 0 L 35.9375 0 L 32.359375 -9.03125 L 14.5625 -9.03125 L 11.171875 0 L -0.90625 0 Z M 23.59375 -33.734375 L 17.734375 -17.9375 L 29.3125 -17.9375 Z M 23.59375 -33.734375 "/></g></g></g><g fill="#ffffff" fill-opacity="1"><g transform="translate(175.731837, 103.249251)"><g><path d="M 4.75 0 L 4.75 -46.015625 L 23.0625 -46.015625 C 25.75 -46.015625 28.257812 -45.644531 30.59375 -44.90625 C 32.9375 -44.164062 34.878906 -42.914062 36.421875 -41.15625 C 37.960938 -39.40625 38.734375 -37.082031 38.734375 -34.1875 C 38.734375 -31.71875 38.0625 -29.632812 36.71875 -27.9375 C 35.375 -26.25 33.53125 -25.015625 31.1875 -24.234375 L 31.1875 -24.109375 C 32.96875 -23.804688 34.570312 -23.1875 36 -22.25 C 37.425781 -21.320312 38.550781 -20.097656 39.375 -18.578125 C 40.195312 -17.066406 40.609375 -15.335938 40.609375 -13.390625 C 40.609375 -10.222656 39.785156 -7.644531 38.140625 -5.65625 C 36.492188 -3.664062 34.359375 -2.222656 31.734375 -1.328125 C 29.117188 -0.441406 26.226562 0 23.0625 0 Z M 21.4375 -27.6875 C 23.519531 -27.6875 25.132812 -28.117188 26.28125 -28.984375 C 27.4375 -29.847656 28.015625 -31.082031 28.015625 -32.6875 C 28.015625 -34.25 27.425781 -35.382812 26.25 -36.09375 C 25.082031 -36.8125 23.304688 -37.171875 20.921875 -37.171875 L 15.46875 -37.171875 L 15.46875 -27.6875 Z M 21.703125 -8.96875 C 23.867188 -8.96875 25.707031 -9.367188 27.21875 -10.171875 C 28.738281 -10.972656 29.5 -12.390625 29.5 -14.421875 C 29.5 -16.242188 28.816406 -17.546875 27.453125 -18.328125 C 26.085938 -19.109375 24.148438 -19.5 21.640625 -19.5 L 15.46875 -19.5 L 15.46875 -8.96875 Z M 21.703125 -8.96875 "/></g></g></g><g fill="#ffffff" fill-opacity="1"><g transform="translate(224.338211, 103.249251)"><g><path d="M 27.546875 0 L 16.4375 0 L -0.96875 -46.015625 L 11.5 -46.015625 L 22.15625 -13.390625 L 22.421875 -13.390625 L 33.015625 -46.015625 L 45.296875 -46.015625 Z M 27.546875 0 "/></g></g></g><g fill="#ffffff" fill-opacity="1"><g transform="translate(273.269402, 103.249251)"><g><path d="M 27.625 1.234375 C 22.851562 1.234375 18.570312 0.207031 14.78125 -1.84375 C 10.988281 -3.90625 8.007812 -6.785156 5.84375 -10.484375 C 3.675781 -14.191406 2.59375 -18.429688 2.59375 -23.203125 C 2.59375 -28.003906 3.664062 -32.222656 5.8125 -35.859375 C 7.957031 -39.503906 10.9375 -42.3125 14.75 -44.28125 C 18.5625 -46.257812 22.851562 -47.25 27.625 -47.25 C 32.425781 -47.25 36.722656 -46.257812 40.515625 -44.28125 C 44.304688 -42.3125 47.285156 -39.503906 49.453125 -35.859375 C 51.617188 -32.222656 52.703125 -28.003906 52.703125 -23.203125 C 52.703125 -18.429688 51.617188 -14.191406 49.453125 -10.484375 C 47.285156 -6.785156 44.296875 -3.90625 40.484375 -1.84375 C 36.671875 0.207031 32.382812 1.234375 27.625 1.234375 Z M 27.625 -8.90625 C 30.175781 -8.90625 32.445312 -9.507812 34.4375 -10.71875 C 36.4375 -11.9375 38 -13.640625 39.125 -15.828125 C 40.25 -18.015625 40.8125 -20.472656 40.8125 -23.203125 C 40.8125 -25.835938 40.25 -28.226562 39.125 -30.375 C 38 -32.519531 36.4375 -34.195312 34.4375 -35.40625 C 32.445312 -36.625 30.175781 -37.234375 27.625 -37.234375 C 25.0625 -37.234375 22.785156 -36.625 20.796875 -35.40625 C 18.804688 -34.195312 17.253906 -32.53125 16.140625 -30.40625 C 15.035156 -28.289062 14.484375 -25.890625 14.484375 -23.203125 C 14.484375 -20.472656 15.035156 -18.015625 16.140625 -15.828125 C 17.253906 -13.640625 18.804688 -11.9375 20.796875 -10.71875 C 22.785156 -9.507812 25.0625 -8.90625 27.625 -8.90625 Z M 27.625 -8.90625 "/></g></g></g><g fill="#ffffff" fill-opacity="1"><g transform="translate(333.962132, 103.249251)"><g><path d="M 4.75 0 L 4.75 -46.015625 L 22.296875 -46.015625 C 25.492188 -46.015625 28.40625 -45.554688 31.03125 -44.640625 C 33.65625 -43.734375 35.789062 -42.25 37.4375 -40.1875 C 39.082031 -38.132812 39.90625 -35.441406 39.90625 -32.109375 C 39.90625 -29.066406 39.054688 -26.460938 37.359375 -24.296875 C 35.671875 -22.140625 33.332031 -20.601562 30.34375 -19.6875 L 42.375 0 L 29.375 0 L 19.4375 -18.265625 L 15.65625 -18.265625 L 15.65625 0 Z M 20.859375 -26.3125 C 23.109375 -26.3125 25.015625 -26.710938 26.578125 -27.515625 C 28.140625 -28.316406 28.921875 -29.78125 28.921875 -31.90625 C 28.921875 -33.851562 28.203125 -35.195312 26.765625 -35.9375 C 25.335938 -36.675781 23.585938 -37.046875 21.515625 -37.046875 L 15.59375 -37.046875 L 15.59375 -26.3125 Z M 20.859375 -26.3125 "/></g></g></g><g fill="#ffffff" fill-opacity="1"><g transform="translate(382.438547, 103.249251)"><g><path d="M 15.53125 0 L 4.75 0 L 4.75 -46.015625 L 17.421875 -46.015625 L 35.875 -15.984375 L 36.0625 -15.984375 L 35.8125 -46.015625 L 46.59375 -46.015625 L 46.59375 0 L 33.984375 0 L 15.46875 -30.09375 L 15.265625 -30.09375 Z M 15.53125 0 "/></g></g></g><path fill="#ffffff" d="M 105.835938 97.621094 C 105.289062 101.863281 102.894531 105.121094 98.984375 106.453125 C 95.046875 107.796875 90.605469 106.808594 88.234375 103.453125 C 85.203125 99.167969 82.503906 94.648438 79.898438 90.101562 C 78.640625 87.902344 77.589844 87.488281 75.15625 88.746094 C 63.648438 94.6875 51.105469 91.175781 44.476562 80.359375 C 43.625 78.972656 42.785156 77.574219 41.914062 76.195312 C 40.871094 74.53125 39.519531 73.1875 37.375 74.339844 C 35.257812 75.476562 35.605469 77.253906 36.632812 78.992188 C 37.832031 81.019531 39.046875 83.035156 40.238281 85.0625 C 42.09375 88.214844 42.074219 91.375 40.210938 94.519531 C 38.6875 97.085938 37.214844 99.6875 35.59375 102.195312 C 32.515625 106.953125 26.820312 108.375 22.007812 105.679688 C 17.207031 102.988281 15.917969 97.597656 18.941406 92.617188 C 25.191406 82.324219 31.4375 72.035156 37.746094 61.773438 C 42.402344 54.203125 51.140625 54.308594 55.757812 61.941406 C 59.644531 68.367188 63.480469 74.828125 67.457031 81.203125 C 68.066406 82.183594 69.210938 83.164062 70.304688 83.453125 C 71.074219 83.660156 72.71875 82.902344 73.011719 82.203125 C 73.425781 81.222656 73.332031 79.691406 72.792969 78.746094 C 69.648438 73.253906 66.316406 67.859375 63.042969 62.4375 C 59.765625 57.011719 56.363281 51.65625 53.226562 46.160156 C 49.8125 40.183594 52.433594 34.042969 58.964844 32.226562 C 63.246094 31.039062 67.410156 32.714844 70.046875 37.011719 C 75.253906 45.5 80.289062 54.085938 85.453125 62.601562 C 91.183594 72.039062 97.019531 81.417969 102.703125 90.886719 C 103.976562 93.003906 104.804688 95.367188 105.835938 97.621094 Z M 105.835938 97.621094 " fill-opacity="1" fill-rule="evenodd"/></svg>'''

FAVICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" fill="#0a0a0a" rx="4"/>
  <text x="12" y="46" font-family="Georgia,serif" font-size="34" font-weight="700" fill="#5A7D9A">A</text>
</svg>'''

def ensure_assets():
    (EMPIRE_DIR / "logo.svg").write_text(LOGO_SVG, encoding="utf-8")
    (EMPIRE_DIR / "favicon.svg").write_text(FAVICON_SVG, encoding="utf-8")

# ── GITHUB DEPLOY ──────────────────────────────────────────────────────────
def push_single_file(path_in_repo, content_bytes_or_str):
    if not repo: print("   GitHub not configured"); return False
    if isinstance(content_bytes_or_str, str): content_bytes_or_str = content_bytes_or_str.encode('utf-8')
    try:
        try:
            ref = repo.get_git_ref("heads/main")
        except:
            ref = repo.get_git_ref("heads/master")
        parent = repo.get_git_commit(ref.object.sha)
        tree = repo.create_git_tree([InputGitTreeElement(path=path_in_repo, mode="100644", type="blob", content=content_bytes_or_str.decode('utf-8', errors='replace'))], base_tree=repo.get_git_tree(parent.sha, recursive=True))
        commit = repo.create_git_commit(f"Abvorn auto-deploy {datetime.now().strftime('%Y-%m-%d %H:%M')}", tree, [parent])
        ref.edit(commit.sha)
        return True
    except Exception as e:
        print(f"   Push failed: {e}")
        return False

def push_directory_tree(local_dir, prefix=""):
    if not repo: print("   GitHub not configured"); return False
    elements = []
    for f in sorted(local_dir.rglob("*")):
        if f.is_file() and f.suffix in ('.html','.json','.xml','.css','.js','.png','.jpg','.svg','.ico','.md','.txt'):
            rel = f.relative_to(local_dir)
            repo_path = f"{prefix}/{rel}" if prefix else str(rel)
            try:
                content = f.read_bytes().decode('utf-8', errors='replace')
                elements.append(InputGitTreeElement(path=repo_path, mode="100644", type="blob", content=content))
            except: pass
    if not elements: return False
    try:
        if not repo: raise Exception("GitHub not configured")
        try: ref = repo.get_git_ref("heads/main")
        except: ref = repo.get_git_ref("heads/master")
        parent = repo.get_git_commit(ref.object.sha)
        tree = repo.create_git_tree(elements, base_tree=repo.get_git_tree(parent.sha, recursive=True))
        commit = repo.create_git_commit(f"Abvorn auto-deploy {datetime.now().strftime('%Y-%m-%d %H:%M')}", tree, [parent])
        ref.edit(commit.sha)
        return True
    except Exception as e:
        print(f"   Directory push failed: {e}")
        return False

def deploy_and_ping():
    state = load_state()
    if not state['completed'] and not state.get('deployed'):
        if state.get('deployed'):
            push_single_file("index.html", build_homepage(state))
        return []
    sitemap_urls = []
    all_elements = []
    deployed_slugs = []
    for slug in state['completed']:
        niche_folder = EMPIRE_DIR / slug
        if not niche_folder.exists(): continue
        for f in niche_folder.rglob("*"):
            if f.is_file() and f.suffix in ('.html','.json','.xml'):
                rel = str(f.relative_to(EMPIRE_DIR))
                all_elements.append((rel, f.read_bytes().decode('utf-8', errors='replace')))
                if f.name == "index.html":
                    sitemap_urls.append(slug)
                    if slug not in deployed_slugs: deployed_slugs.append(slug)
    if not all_elements:
        print("   No new content to deploy.")
        return []
    new_slugs = [s for s in sitemap_urls if s not in state.get('deployed', [])]
    state['deployed'] = list(dict.fromkeys(state.get('deployed', []) + sitemap_urls))
    save_state(state)

    # Ensure logo/favicon assets exist
    ensure_assets()

    # Build homepage, RSS, sitemap, trending
    build_homepage(state)
    build_rss_feed(state)
    build_sitemap(state)
    build_trending_json(state)

    # Clear completed after deploy to prevent duplicates
    state['completed'] = []

    # Include empire-level files
    for f in EMPIRE_DIR.glob("*"):
        if f.is_file() and f.suffix in ('.html','.json','.xml','.css','.js','.png','.svg','.ico'):
            rel = f.name
            if rel not in [e[0] for e in all_elements]:
                all_elements.append((rel, f.read_bytes().decode('utf-8', errors='replace')))

    # ── SEO PRE-DEPLOY AUDIT ──
    seo_issues = seo_audit_pages(new_slugs or sitemap_urls)
    if seo_issues:
        report_path = EMPIRE_DIR / "seo_issues.log"
        report_path.write_text(f"SEO Audit {datetime.now().isoformat()}\n" + "\n".join(seo_issues))
        print(f"   ⚠ SEO issues logged — continuing deploy ({len(seo_issues)} issues)")

    try:
        try: ref = repo.get_git_ref("heads/main")
        except: ref = repo.get_git_ref("heads/master")
        parent = repo.get_git_commit(ref.object.sha)
        tree_elements = [InputGitTreeElement(path=p, mode="100644", type="blob", content=c) for p, c in all_elements]
        tree = repo.create_git_tree(tree_elements, base_tree=repo.get_git_tree(parent.sha, recursive=True))
        commit = repo.create_git_commit(f"Abvorn deploy: {len(new_slugs)} niches, {len(all_elements)} files ({datetime.now().strftime('%Y-%m-%d %H:%M')})", tree, [parent])
        ref.edit(commit.sha)
        print(f"   Deployed {len(new_slugs)} new niches ({len(all_elements)} files).")
        msg = f"Deployed: {len(new_slugs)} new niche(s)" + (f" — {', '.join(new_slugs[:3])}" if new_slugs else "")
        notify(msg)
    except Exception as e:
        print(f"   Deploy failed: {e}")
        notify(f"Deploy FAILED: {str(e)[:100]}")
        return new_slugs

    # Post to social media and resolve predictions
    for slug in new_slugs:
        niche_name = slug.replace('_', ' ').title()
        try: publish_social_media(slug, niche_name)
        except: pass
        try: resolve_prediction(niche_name, actual_conversions=1, actual_traffic=50)
        except: pass

    # ── GA4 ANALYTICS FEEDBACK LOOP ──
    state = load_state()
    analytics = pull_ga4_analytics()
    if analytics:
        perf = state.setdefault('performance', {})
        for slug, data in analytics.items():
            if slug not in perf: perf[slug] = {}
            entry = perf[slug] if isinstance(perf[slug], dict) else {}
            entry['ga4_views'] = data.get('views', 0)
            entry['ga4_users'] = data.get('users', 0)
            entry['ga4_avg_duration'] = data.get('avg_duration', 0)
            # Weight score: views * 1 + users * 2 + normalised duration
            score = data.get('views', 0) + data.get('users', 0) * 2 + data.get('avg_duration', 0) / 10
            entry['ga4_score'] = round(score, 1)
            perf[slug] = entry
        save_state(state)

        # ── PERSONA PERFORMANCE ATTRIBUTION ──
        for slug, data in analytics.items():
            meta_file = EMPIRE_DIR / slug / "posts_meta.json"
            if not meta_file.exists(): continue
            try:
                posts = json.loads(meta_file.read_text())
                persona_ids = set(p.get('persona_id','') for p in posts if p.get('persona_id'))
                views = data.get('views', 0)
                users = data.get('users', 0)
                if persona_ids:
                    per_persona_views = max(views // len(persona_ids), 1)
                    per_persona_users = max(users // len(persona_ids), 1)
                    for pid in persona_ids:
                        try: track_persona_outcome(pid, quality_score=0, views=per_persona_views, users=per_persona_users)
                        except: pass
            except: pass

        top = sorted(analytics.items(), key=lambda x: x[1]['views'], reverse=True)[:3]
        top_strs = [f"{s}({d['views']} views)" for s, d in top]
        print(f"   GA4 top niches: {', '.join(top_strs)}")

    return new_slugs

# ── COMPOSIO SOCIAL MEDIA AUTOMATION ───────────────────────────────────────
SOCIAL_PLATFORMS = {
    "x": {"actions": ["TWITTER_CREATE_TWEET", "TWITTER_POST_TWEET", "X_CREATE_TWEET"], "label": "X"},
    "instagram": {"actions": ["INSTAGRAM_CREATE_MEDIA_POST", "INSTAGRAM_CREATE_POST", "INSTAGRAM_UPLOAD_MEDIA"], "label": "Instagram"},
    "linkedin": {"actions": ["LINKEDIN_CREATE_POST", "LINKEDIN_CREATE_ARTICLE", "LINKEDIN_POST_CREATE"], "label": "LinkedIn"},
    "facebook": {"actions": ["FACEBOOK_CREATE_POST", "FACEBOOK_POST_CREATE"], "label": "Facebook"},
    "tiktok": {"actions": ["TIKTOK_CREATE_VIDEO", "TIKTOK_UPLOAD_VIDEO"], "label": "TikTok"},
}

def publish_social_media(slug, niche_name):
    if not composio: return logger.warning("Composio not available, skipping social media.")
    state = load_state()
    posted = state.setdefault('social_posted', [])
    if slug in posted: return
    socials_file = EMPIRE_DIR / slug / "socials.json"
    if not socials_file.exists(): return
    try: socials = json.loads(socials_file.read_text())
    except: return
    results = []
    for platform_key, content in socials.items():
        if not content or platform_key not in SOCIAL_PLATFORMS: continue
        cfg = SOCIAL_PLATFORMS[platform_key]
        content_text = str(content)[:5000]

        # Recursive query chain: Captain consults General before posting
        for gname in list(state.get('generals', {}).keys()):
            gen = state['generals'][gname]
            if platform_key in gen.get('captains', {}):
                try:
                    advice, source = captain_query(gname, platform_key, f"What is the best way to post about '{niche_name}' on {cfg['label']}?")
                    if advice and len(advice) > 10:
                        logger.info(f"  Captain of {cfg['label']} consulted {source}: {advice[:80]}...")
                        if len(advice) > 50: content_text = advice[:5000]
                except: pass
                try: captain_execute(gname, platform_key, "post", {"content": content_text[:100]})
                except: pass
                break

        success = False
        for action_name in cfg["actions"]:
            try:
                action = getattr(Action, action_name, None)
                if not action: continue
                params = {"text": content_text}
                if platform_key == "instagram": params = {"caption": content_text}
                if platform_key in ("x", "twitter"): params = {"text": content_text}
                composio.execute_action(action, params=params)
                results.append(f"{cfg['label']}: posted")
                success = True
                break
            except Exception as e:
                logger.debug(f"  {cfg['label']} via {action_name} failed: {str(e)[:60]}")
        if not success:
            results.append(f"{cfg['label']}: skipped (no action)")
    posted.append(slug)
    save_state(state)
    msg = f"Social posted for '{niche_name}': " + ", ".join(results)
    if results: logger.info(msg)
    return results

# ── TREND RE-EVALUATION ────────────────────────────────────────────────────
def re_evaluate_trends(state):
    drops = []
    for slug in list(state.get('deployed', []))[:10]:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(f"{slug.replace('_',' ')} 2025", max_results=3))
                if not results:
                    drops.append(slug)
        except: pass
    return drops

# ── SKILL EVOLUTION ────────────────────────────────────────────────────────
SKILLS_SCOREBOARD_FILE = SKILLS_DIR / "scoreboard.json"

def run_skill_evolution():
    perf = load_state().get('performance', {})
    if not perf: return None
    board = {}
    if SKILLS_SCOREBOARD_FILE.exists(): board = json.loads(SKILLS_SCOREBOARD_FILE.read_text())
    avg_conversions = sum(v.get('conversions', 0) if isinstance(v, dict) else 0 for v in perf.values()) / max(len(perf), 1)
    archived = []
    for skill_file in sorted(SKILLS_DIR.glob("*.md")):
        if skill_file.stem in ("general_persuasion_soul",) or skill_file.stem.startswith("candidate_"): continue
        entry = board.get(skill_file.stem, {"observations": 0, "score": 0.0, "candidate": False})
        if entry.get("candidate") and entry.get("observations", 0) >= 5 and entry.get("score", 0) < avg_conversions * 0.5:
            archive_dir = SKILLS_DIR / "archived"
            archive_dir.mkdir(exist_ok=True)
            shutil.move(str(skill_file), str(archive_dir / skill_file.name))
            archived.append(skill_file.stem)
    proposed = None
    if not any(v.get("candidate") for v in board.values()) and perf:
        top = sorted(perf.items(), key=lambda kv: kv[1].get('conversions', 0) if isinstance(kv[1], dict) else 0, reverse=True)[:3]
        draft = ask_ai(f"Based on top niches: {json.dumps(top)}, write ONE short new content/marketing skill (max 300 words, markdown) for our AI writers. Be specific and actionable.", use_soul=True)
        if draft:
            name = f"candidate_{datetime.now().strftime('%Y%m%d%H%M')}"
            (SKILLS_DIR / f"{name}.md").write_text(draft)
            board[name] = {"observations": 0, "score": 0.0, "candidate": True}
            proposed = name
    SKILLS_SCOREBOARD_FILE.write_text(json.dumps(board, indent=2))
    if archived or proposed: return {"archived": archived, "proposed": proposed}
    return None

def propose_code_patch():
    state = load_state()
    last_proposal = state.get('last_proposal_time', '')
    days_since = 999
    if last_proposal:
        try: days_since = (datetime.now() - datetime.fromisoformat(last_proposal)).days
        except: pass
    if days_since < 7:
        return None  # Only propose once per week

    failures = state.get('failed', [])
    performances = state.get('performance', {})
    deployed = state.get('deployed', [])
    completed = state.get('completed', [])

    error_context = []
    for slug in (failures[-3:] if failures else []):
        if not slug: continue
        niche_folder = EMPIRE_DIR / slug
        err_file = niche_folder / "error.log"
        if err_file.exists():
            try: error_context.append(f"{slug}: {err_file.read_text()[:200]}")
            except: error_context.append(f"{slug}: (error reading log)")
        else:
            error_context.append(f"{slug}: (no error log)")

    # Gather performance data for context
    perf_summary = ""
    if performances:
        top = sorted(performances.items(), key=lambda x: x[1].get('conversions', 0) if isinstance(x[1], dict) else 0, reverse=True)[:3]
        bottom = sorted(performances.items(), key=lambda x: x[1].get('conversions', 0) if isinstance(x[1], dict) else 0)[:3]
        perf_summary = f"\nTop performers: {json.dumps(top)}\nLow performers: {json.dumps(bottom)}"

    prompt = f"""You are an AI code reviewer for the Abvorn affiliate content system.
Current state: {len(deployed)} deployed, {len(completed)} completed, {len(failures)} failed, {len(performances)} tracked niches.
{perf_summary}
Error context: {' | '.join(error_context) if error_context else 'No recent errors (system stable)'}

Based on THIS data, suggest ONE concrete improvement. If system is stable, suggest a performance optimization or new feature (e.g., A/B testing headlines, new content format, SEO improvement). Be specific and actionable. Respond in 3-5 sentences. Do NOT invent fake function names."""

    suggestion = ask_ai(prompt, use_soul=False)
    if not suggestion: return None
    state['last_proposal_time'] = datetime.now().isoformat()
    save_state(state)
    try:
        push_single_file(f"proposals/{datetime.now().strftime('%Y%m%d_%H%M')}.md", f"# Auto-drafted improvement proposal\n\n{suggestion}\n")
        notify(f"New improvement proposal drafted.")
    except: pass
    return suggestion

def send_executive_report(state, new_slugs, link_repairs, trend_drops, skill_evolved):
    lines = ["ABVORN — Executive Cycle Report", datetime.now().strftime("%Y-%m-%d %H:%M"),"",f"Deployed: {len(new_slugs)} niche(s)" + (f" — {', '.join(new_slugs[:5])}" if new_slugs else ""),f"Links repaired: {link_repairs}",f"Trends dropping: {len(trend_drops)}" + (f" — {', '.join(trend_drops[:5])}" if trend_drops else ""),f"Skill evolution: {skill_evolved if skill_evolved else 'no changes this cycle'}",f"Failed niches (total): {len(state.get('failed', []))}"]
    perf = load_state().get('performance', {})
    top = sorted(perf.items(), key=lambda x: x[1].get('conversions', 0) if isinstance(x[1], dict) else 0, reverse=True)[:3]
    if top: lines.append("Top niches: " + ", ".join(f"{s}({d.get('conversions',0)})" for s,d in top))
    generals = state.get('generals', {})
    if generals:
        lines.append(""); lines.append("Generals:")
        for name, gen in generals.items():
            lines.append(f"  {gen.get('name',name)} ({gen.get('status','?')}) — {gen.get('domain','?')}")
    notify("\n".join(str(l) for l in lines))

# ── EXECUTE ─────────────────────────────────────────────────────────────────
print("Abvorn Deployer & Evolution v13 starting...\n")
print("Polling CEO commands...")
poll_ceo_commands()

new_slugs = deploy_and_ping()

trend_drops = re_evaluate_trends(load_state())

state = load_state()
if not state.get('enterprise_structure') or 'roles' not in state['enterprise_structure'].get('structure', {}):
    design_enterprise_structure(state)

new_general = spawn_general_if_needed(state)

skill_evolved = run_skill_evolution()

# Evaluate all Captains across all Generals each cycle
try:
    state = load_state()
    for gname, gen in state.get('generals', {}).items():
        if gen.get('captains'):
            for pname in gen['captains']:
                evaluate_captain(gname, pname)
except: pass

propose_code_patch()

state = load_state()
send_executive_report(state, new_slugs, 0, trend_drops, skill_evolved)

print("Abvorn cycle complete. Fortress fortified, Generals deployed, design elevated.")
