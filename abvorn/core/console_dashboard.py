"""console_dashboard.py — Abvorn Console dashboard generator.

Reads all real data sources and renders a self-contained HTML page
(and a JSON snapshot) for the command center.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not read {path}: {e}")
        return None


def _read_cycle_state() -> Dict[str, Any]:
    data = _read_json(PROJECT_DIR / "cycle_state.json") or {}
    niches = data.get("niches", []) or []
    total_posts = sum(int(n.get("posts", 0) or 0) for n in niches)
    return {
        "total_niches": len(niches),
        "total_articles": total_posts,
        "articles_per_week": total_posts / 4.0 if total_posts else 0.0,
        "queue_size": len(data.get("queue", []) or []),
        "last_processed": data.get("last_processed", "None"),
        "affiliate_clicks": int(data.get("affiliate_clicks", 0) or 0),
        "niches": niches,
    }


def _read_economic_surplus() -> Dict[str, Any]:
    """Economic records live in data/surplus/economic_records.json."""
    path = PROJECT_DIR / "data" / "surplus" / "economic_records.json"
    records = _read_json(path) or []
    if not isinstance(records, list):
        records = []
    total_revenue = sum(float(r.get("revenue", 0) or 0) for r in records)
    total_cost = sum(float(r.get("costs", 0) or 0) for r in records)
    total_profit = sum(float(r.get("profit", 0) or 0) for r in records)
    roi = (total_profit / total_cost) if total_cost > 0 else (total_profit if total_profit > 0 else 0.0)
    return {
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "roi": roi,
        "records": len(records),
    }


def _read_clicks() -> Dict[str, Any]:
    path = PROJECT_DIR / "data" / "clicks.db"
    try:
        if not path.exists():
            return {"total_clicks": 0, "by_article": {}}
        conn = sqlite3.connect(str(path))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM clicks")
        total = cur.fetchone()[0] or 0
        cur.execute("SELECT article_id, COUNT(*) FROM clicks GROUP BY article_id ORDER BY 2 DESC")
        by_article = {row[0]: row[1] for row in cur.fetchall()}
        conn.close()
        return {"total_clicks": total, "by_article": by_article}
    except Exception as e:
        logger.warning(f"Could not read clicks.db: {e}")
        return {"total_clicks": 0, "by_article": {}}


def _read_core_state() -> Dict[str, Any]:
    data = _read_json(PROJECT_DIR / "data" / "relentless_state.json") or {}
    history = data.get("history", []) or []
    outcomes = []
    outcomes_path = PROJECT_DIR / "data" / "outcomes.jsonl"
    if outcomes_path.exists():
        for line in outcomes_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            outcomes.append({
                "timestamp": o.get("timestamp"),
                "action": o.get("action", "action"),
                "result": str(o.get("result", "")),
                "verified": bool(o.get("verified", False)),
            })
    merged = outcomes + history
    merged.sort(key=lambda r: str(r.get("timestamp", "")), reverse=True)
    return {
        "drive_score": float(data.get("drive_score", 0.0) or 0.0),
        "ambition_level": float(data.get("ambition_level", 0.5) or 0.5),
        "last_action": data.get("action", data.get("last_action", "None")),
        "gap": float(data.get("gap", 0.0) or 0.0),
        "status": data.get("status", "unknown"),
        "days_flat": int(data.get("days_flat", 0) or 0),
        "recent_actions": merged[:12],
    }


def _read_verdict_weights() -> Dict[str, Any]:
    data = _read_json(PROJECT_DIR / "data" / "verdict_weights.json")
    if not isinstance(data, dict):
        return {}
    return data


def _read_win_metrics() -> Dict[str, Any]:
    try:
        from abvorn.core.win_sh_bridge import get_win_sh_bridge

        bridge = get_win_sh_bridge()
        if not bridge.is_ready():
            return {"active_loops": 0, "total_runs": 0, "total_outcomes": 0, "total_completed": 0, "loops": {}}
        metrics = bridge.get_all_metrics()
        loops = {k: v for k, v in metrics.items() if isinstance(v, dict) and "runs" in v}
        return {
            "active_loops": len(loops),
            "total_runs": int(metrics.get("total_runs", 0) or 0),
            "total_outcomes": int(metrics.get("total_outcomes", 0) or 0),
            "total_completed": int(metrics.get("total_completed", 0) or 0),
            "loops": loops,
        }
    except Exception as e:
        logger.warning(f"win.sh metrics not available: {e}")
        return {"active_loops": 0, "total_runs": 0, "total_outcomes": 0, "total_completed": 0, "loops": {}}


def _read_fable_state() -> Dict[str, Any]:
    data = _read_json(PROJECT_DIR / "data" / "fable_state.json") or {}
    return {
        "total_plans": len(data.get("plans", []) or []),
        "total_verifications": len(data.get("verifications", []) or []),
        "total_learnings": len(data.get("learnings", []) or []),
        "last_cycle": data.get("last_cycle", "Never"),
        "agent": data.get("agent", "opencode"),
    }


def _read_memory_state() -> Dict[str, Any]:
    data = _read_json(PROJECT_DIR / "data" / "neural_memory_state.json") or {}
    return {
        "entities": int(data.get("entities", 0) or 0),
        "relationships": int(data.get("relationships", 0) or 0),
        "insights": len(data.get("insights", []) or []),
        "queries": len(data.get("queries", []) or []),
        "correlations": len(data.get("correlations", []) or []),
        "last_ingestion": data.get("last_ingestion", "Never"),
    }


def _read_spawn_state() -> Dict[str, Any]:
    data = _read_json(PROJECT_DIR / "data" / "spawn_state.json") or {}
    return {
        "role": "leader" if data.get("leader") and data.get("last_heartbeat") else "awaiting_leader",
        "leader": data.get("leader", "None"),
        "followers": len(data.get("followers", []) or []),
        "last_heartbeat": data.get("last_heartbeat", "Never"),
    }


def _read_lineage() -> Dict[str, Any]:
    data = _read_json(PROJECT_DIR / "data" / "genesis" / "lineage.json") or {}
    return {
        "current_version": int(data.get("current_version", 1) or 1),
        "generations": len(data.get("generations", []) or []),
        "last_transfer": data.get("last_transfer", "Never"),
        "last_death": data.get("last_death", "Never"),
    }


def _read_unified_db_summary() -> Dict[str, Any]:
    try:
        from abvorn.core.unified_database import get_unified_db

        return get_unified_db().get_summary()
    except Exception as e:
        logger.warning(f"Unified DB unavailable: {e}")
        return {"total_subscribers": 0, "active_alerts": 0, "total_profit": 0, "total_campaigns": 0}


def _read_brain_state() -> Dict[str, Any]:
    try:
        from abvorn.core.brain import get_brain

        brain = get_brain()
        report = brain.get_category_report()
        memory_state = brain.memory.get_state()
        return {
            "status": "ready" if brain.is_ready else "building",
            "entities": int(memory_state.get("entities", 0) or 0),
            "relationships": int(memory_state.get("relationships", 0) or 0),
            "categories": len(report),
            "books": sum(report.values()),
        }
    except Exception as e:
        logger.warning(f"Brain state unavailable: {e}")
        return {"status": "unavailable", "entities": 0, "relationships": 0, "categories": 0, "books": 0}


def _read_gsc_state() -> Dict[str, Any]:
    """Read the latest Google Search Console summary written by the ingestor."""
    data = _read_json(PROJECT_DIR / "data" / "gsc_latest_summary.json") or {}
    return {
        "enabled": bool(data.get("total_clicks") is not None and data.get("timestamp")),
        "total_clicks": int(data.get("total_clicks", 0) or 0),
        "total_impressions": int(data.get("total_impressions", 0) or 0),
        "avg_ctr": float(data.get("avg_ctr", 0.0) or 0.0),
        "avg_position": float(data.get("avg_position", 0.0) or 0.0),
        "days": int(data.get("days", 0) or 0),
        "last_ingestion": data.get("timestamp", "Never"),
    }


def _read_cortex_state() -> Dict[str, Any]:
    """Read Cortex (Obsidian vault) status for the dashboard."""
    try:
        from abvorn.core.cortex_watcher import cortex_status, get_recent_journal

        status = cortex_status()
        recent = get_recent_journal(limit=3)
        return {
            "enabled": bool(status.get("enabled")),
            "watching": bool(status.get("watching")),
            "vault": status.get("vault"),
            "corrections_logged": int(status.get("corrections_logged", 0) or 0),
            "recent_entries": recent,
        }
    except Exception as e:
        logger.warning(f"Cortex state unavailable: {e}")
        return {"enabled": False, "watching": False, "vault": None, "corrections_logged": 0, "recent_entries": []}


def _read_n8n_state() -> Dict[str, Any]:
    """Read n8n reachability for the dashboard (short timeout, never fatal)."""
    try:
        from abvorn.core.n8n_bridge import get_n8n_bridge

        bridge = get_n8n_bridge()
        health = bridge.health()
        return {
            "status": health.get("status"),
            "healthy": bool(health.get("healthy")),
            "n8n_url": health.get("n8n_url"),
        }
    except Exception as e:
        logger.warning(f"n8n state unavailable: {e}")
        return {"status": "error", "healthy": False, "n8n_url": None}


def get_system_status() -> Dict[str, Any]:
    """Gather all metrics from real data sources."""
    cycle = _read_cycle_state()
    econ = _read_economic_surplus()
    clicks = _read_clicks()
    core = _read_core_state()
    win = _read_win_metrics()
    fable = _read_fable_state()
    memory = _read_memory_state()
    spawn = _read_spawn_state()
    lineage = _read_lineage()
    unified = _read_unified_db_summary()
    brain = _read_brain_state()
    gsc = _read_gsc_state()
    cortex = _read_cortex_state()
    n8n = _read_n8n_state()

    return {
        "timestamp": datetime.now().isoformat(),
        "drive_score": core["drive_score"],
        "ambition_level": core["ambition_level"],
        "last_action": core["last_action"],
        "status": core["status"],
        "days_flat": core["days_flat"],
        "total_niches": cycle["total_niches"],
        "total_articles": cycle["total_articles"],
        "articles_per_week": cycle["articles_per_week"],
        "queue_size": cycle["queue_size"],
        "affiliate_clicks": cycle["affiliate_clicks"],
        "total_revenue": econ["total_revenue"],
        "total_cost": econ["total_cost"],
        "total_profit": econ["total_profit"],
        "roi": econ["roi"],
        "total_clicks": clicks["total_clicks"],
        "verdict_weights": _read_verdict_weights(),
        "recent_actions": core["recent_actions"],
        "win": win,
        "fable": fable,
        "memory": memory,
        "spawn": spawn,
        "lineage": lineage,
        "unified": unified,
        "brain": brain,
        "gsc": gsc,
        "cortex": cortex,
        "n8n": n8n,
    }


# -- Console redesign block (spliced into abvorn/core/console_dashboard.py) --

_CONSOLE_CSS = """
:root{
  --ink:#17120C;
  --panel:#1F1810;
  --panel-2:#241C12;
  --edge:#2C2318;
  --edge-hi:#3A2F20;
  --bone:#E8DFC8;
  --sand:#A89B82;
  --taupe:#8E7C61;
  --brass:#D9A441;
  --amber-deep:#B9772E;
  --brass-soft:rgba(217,164,65,.14);
  --moss:#7FA25C;
  --clay:#B24A3D;
  --font-display:"Chakra Petch","Segoe UI",system-ui,sans-serif;
  --font-mono:"IBM Plex Mono",ui-monospace,Consolas,monospace;
  --r:12px;
}
*{box-sizing:border-box;margin:0;padding:0}
html{background:var(--ink)}
body{
  font-family:var(--font-display);
  background:radial-gradient(1200px 600px at 85% -10%, rgba(217,164,65,.05), transparent 60%), var(--ink);
  color:var(--bone);
  min-height:100vh;
  padding:28px 20px 40px;
}
.shell{max-width:1180px;margin:0 auto;display:grid;gap:16px}
.panel{
  background:linear-gradient(180deg,var(--panel-2),var(--panel));
  border:1px solid var(--edge);
  border-radius:var(--r);
  padding:18px 20px;
  box-shadow:0 1px 0 rgba(255,255,255,.03) inset, 0 12px 30px -18px rgba(0,0,0,.7);
}
.eyebrow{
  font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--sand);
  font-family:var(--font-mono);display:block;
}
.mono{font-family:var(--font-mono)}
.topbar{display:flex;justify-content:space-between;align-items:center;padding:4px 2px 10px}
.brand{display:flex;align-items:center;gap:10px}
.brand-dot{width:9px;height:9px;border-radius:50%;background:var(--brass);box-shadow:0 0 0 4px var(--brass-soft),0 0 14px var(--brass)}
.brand-word{font-weight:700;letter-spacing:.28em;font-size:16px}
.brand-sub{font-family:var(--font-mono);color:var(--taupe);font-size:12px;letter-spacing:.14em}
.topbar-right{display:flex;align-items:center;gap:18px}
.lamp{display:inline-flex;align-items:center;gap:8px;font-family:var(--font-mono);font-size:11px;letter-spacing:.18em;color:var(--sand)}
.lamp-bulb{width:8px;height:8px;border-radius:50%;display:inline-block}
.lamp.alive .lamp-bulb{background:var(--moss);box-shadow:0 0 0 4px rgba(127,162,92,.15),0 0 10px var(--moss)}
.lamp.alive{color:var(--moss)}
.lamp.armed .lamp-bulb{background:var(--brass);box-shadow:0 0 0 4px var(--brass-soft),0 0 10px var(--brass)}
.lamp.armed{color:var(--brass)}
.lamp.idle .lamp-bulb{background:var(--taupe)}
.clock{font-size:12px;color:var(--taupe)}
.pulse-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.pulse-meta{font-size:11px;color:var(--taupe)}
.pulse-svg{width:100%;height:110px;display:block}
.p-grid{stroke:var(--edge);stroke-width:1;stroke-dasharray:2 6}
.p-line{stroke:var(--brass);stroke-width:2}
.p-line.flat{stroke:var(--taupe);stroke-dasharray:6 8}
.p-dot{fill:var(--brass)}
.p-noise{font-family:var(--font-mono);font-size:11px;fill:var(--taupe);letter-spacing:.3em}
.p-sweep{stroke:var(--brass);stroke-width:1;opacity:.35;transform:translateX(var(--sweep,0px));animation:sweep 9s linear infinite}
@keyframes sweep{from{--sweep:0px}to{--sweep:1340px}}
.pulse-foot{font-size:11px;color:var(--taupe);margin-top:8px;text-align:right}
.main-grid{display:grid;grid-template-columns:minmax(300px,420px) 1fr;gap:16px;align-items:stretch}
.gauge-panel{display:flex;flex-direction:column;align-items:center;text-align:center;padding-bottom:22px}
.gauge{width:210px;height:210px}
.g-track{fill:none;stroke:var(--edge-hi);stroke-width:10;stroke-linecap:round}
.g-fill{fill:none;stroke:var(--brass);stroke-width:10;stroke-linecap:round;filter:drop-shadow(0 0 6px rgba(217,164,65,.35))}
.tick{stroke:var(--taupe);stroke-width:1}
.tick.major{stroke:var(--sand);stroke-width:1.5}
.tick-label{font-family:var(--font-mono);font-size:9px;fill:var(--taupe)}
.needle{transform-origin:120px 120px;animation:swing 1s cubic-bezier(.16,.8,.24,1) .1s both}
.needle-line{stroke:var(--bone);stroke-width:3;stroke-linecap:round}
.needle-hub{fill:var(--ink);stroke:var(--brass);stroke-width:3}
@keyframes swing{from{transform:rotate(var(--rot-from))}to{transform:rotate(var(--rot-to))}}
.gauge-readouts{display:flex;gap:34px;margin-top:2px}
.readout{display:flex;flex-direction:column;align-items:center;gap:2px}
.readout-value{font-size:22px;font-weight:500;color:var(--bone)}
.readout-label{font-size:10px;letter-spacing:.16em;color:var(--taupe);text-transform:uppercase}
.ambition{width:100%;margin-top:16px}
.ambition-label{font-size:10px;letter-spacing:.16em;color:var(--sand);display:flex;justify-content:space-between;margin-bottom:6px}
.ambition-track{height:4px;background:var(--edge-hi);border-radius:99px;overflow:hidden}
.ambition-fill{height:100%;background:linear-gradient(90deg,var(--amber-deep),var(--brass));border-radius:99px}
.vitals-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.vital{display:flex;flex-direction:column;justify-content:center;gap:4px}
.vital-value{font-size:34px;font-weight:600;letter-spacing:.01em}
.vital-value.alive{color:var(--moss)}
.vital-sub{font-size:11px;color:var(--taupe)}
.organ-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin-top:12px}
.organ{background:var(--panel);border:1px solid var(--edge);border-radius:10px;padding:12px 14px}
.organ-head{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.organ-tag{font-size:10px;letter-spacing:.12em;color:var(--brass);border:1px solid var(--edge-hi);border-radius:5px;padding:2px 6px}
.organ-name{font-size:13px;font-weight:600;flex:1}
.lamp-dot{width:7px;height:7px;border-radius:50%;background:var(--taupe)}
.lamp-dot.alive{background:var(--moss);box-shadow:0 0 8px var(--moss)}
.lamp-dot.armed{background:var(--brass);box-shadow:0 0 8px var(--brass)}
.organ-rows{display:grid;gap:4px}
.row{display:flex;justify-content:space-between;font-size:12px}
.row-label{color:var(--taupe)}
.row-value{color:var(--sand)}
.bottom-grid{display:grid;grid-template-columns:1fr 1.3fr;gap:16px}
.weight-row{display:flex;align-items:center;gap:10px;margin-top:10px}
.weight-label{width:96px;font-size:12px;color:var(--sand);text-transform:capitalize}
.weight-track{flex:1;height:6px;background:var(--edge-hi);border-radius:99px;overflow:hidden}
.weight-fill{height:100%;background:linear-gradient(90deg,var(--amber-deep),var(--brass));border-radius:99px}
.weight-value{font-size:11px;color:var(--bone);width:40px;text-align:right}
.log{margin-top:8px}
.log-row{display:grid;grid-template-columns:150px 1fr 1fr 24px;gap:10px;align-items:baseline;padding:7px 0;border-bottom:1px dashed var(--edge)}
.log-row:last-child{border-bottom:none}
.log-time{font-size:11px;color:var(--taupe)}
.log-name{font-size:13px;font-weight:600;color:var(--bone)}
.log-result{font-size:12px;color:var(--sand);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.log-mark{text-align:center;color:var(--taupe)}
.log-mark.ok{color:var(--moss)}
.empty{font-size:13px;color:var(--taupe);padding:18px 0;line-height:1.5}
.foot{margin-top:4px;text-align:center;font-size:11px;color:var(--taupe);letter-spacing:.12em}
:focus-visible{outline:2px solid var(--brass);outline-offset:3px;border-radius:4px}
@media (prefers-reduced-motion:reduce){
  .needle{animation:none;transform:rotate(var(--rot-to))}
  .p-sweep{animation:none;opacity:0}
}
@media (max-width:900px){
  .main-grid{grid-template-columns:1fr}
  .gauge{width:190px;height:190px}
  .bottom-grid{grid-template-columns:1fr}
}
@media (max-width:560px){
  body{padding:18px 12px 30px}
  .vitals-grid{grid-template-columns:1fr}
  .topbar{flex-direction:column;align-items:flex-start;gap:10px}
  .log-row{grid-template-columns:1fr;gap:2px;padding:8px 0}
  .organ-grid{grid-template-columns:1fr}
  .brand-sub{display:none}
}
"""


def _fmt_utc(ts) -> str:
    if not ts or str(ts).lower() in ("none", "never", "nan"):
        return "\u2014"
    s = str(ts)
    if len(s) >= 19:
        s = s[:19].replace("T", " ")
    return s


def _parse_dt(ts):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _freshness(hb):
    if not hb or str(hb).lower() in ("none", "never"):
        return ("NO SIGNAL", "idle")
    try:
        dt = _parse_dt(hb)
        if dt is None:
            return ("NO SIGNAL", "idle")
        age = datetime.now(timezone.utc) - dt
        if age < timedelta(hours=36):
            return ("ACTIVE", "alive")
        if age < timedelta(days=7):
            return ("STALE", "armed")
        return ("OFFLINE", "idle")
    except Exception:
        return ("NO SIGNAL", "idle")


def _organ_state(alive_v, armed_v) -> str:
    try:
        if int(alive_v) > 0:
            return "alive"
    except (TypeError, ValueError):
        pass
    try:
        if int(armed_v) > 0:
            return "armed"
    except (TypeError, ValueError):
        pass
    return "idle"


def _polar(cx, cy, r, deg):
    import math
    a = math.radians(deg)
    return (cx + r * math.cos(a), cy + r * math.sin(a))


def _arc(cx, cy, r, d0, d1):
    large = 1 if (d1 - d0) > 180 else 0
    x0, y0 = _polar(cx, cy, r, d0)
    x1, y1 = _polar(cx, cy, r, d1)
    return f"M{x0:.1f} {y0:.1f} A {r} {r} 0 {large} 1 {x1:.1f} {y1:.1f}"


def _gauge_svg(score: float) -> str:
    cx, cy, r = 120.0, 120.0, 96.0
    S, E = -210.0, 30.0
    t = max(0.0, min(1.0, score))
    target = S + (E - S) * t
    parts = [f'<svg class="gauge" viewBox="0 0 240 240" role="img" aria-label="Drive score {t:.2f}">']
    parts.append(f'<path d="{_arc(cx, cy, r, S, E)}" class="g-track"/>')
    if target - S > 0.5:
        parts.append(f'<path d="{_arc(cx, cy, r, S, target)}" class="g-fill"/>')
    ticks = []
    for i in range(11):
        deg = S + (E - S) * i / 10.0
        major = i % 2 == 0
        r0, r1 = (r - 4, r - 15) if major else (r - 4, r - 10)
        x0, y0 = _polar(cx, cy, r0, deg)
        x1, y1 = _polar(cx, cy, r1, deg)
        ticks.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" class="tick{" major" if major else ""}"/>')
    parts.append("".join(ticks))
    for frac, lab in [(0.0, "0"), (0.25, ".25"), (0.5, ".5"), (0.75, ".75"), (1.0, "1.0")]:
        deg = S + (E - S) * frac
        x, y = _polar(cx, cy, r - 30, deg)
        parts.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" class="tick-label">{lab}</text>')
    nx0, ny0 = _polar(cx, cy, 20, S)
    nx1, ny1 = _polar(cx, cy, r - 38, S)
    parts.append(
        f'<g class="needle" style="--rot-from:0deg;--rot-to:{target - S:.1f}deg" aria-hidden="true">'
        f'<line x1="{nx0:.1f}" y1="{ny0:.1f}" x2="{nx1:.1f}" y2="{ny1:.1f}" class="needle-line"/>'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6.5" class="needle-hub"/></g>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _pulse_svg(events, span_days: int = 7) -> str:
    W, H, base = 1400, 110, 80
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=span_days)
    margin = 30
    parts = [f'<svg class="pulse-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">']
    for gy in (40, 60, 80):
        parts.append(f'<line x1="{margin}" y1="{gy}" x2="{W - margin}" y2="{gy}" class="p-grid"/>')

    def _x(ts):
        dt = _parse_dt(ts)
        if dt is None:
            return None
        frac = (dt - start).total_seconds() / (now - start).total_seconds()
        frac = max(0.0, min(1.0, frac))
        return margin + frac * (W - 2 * margin)

    xs = [_x(ts) for ts in events]
    xs = [x for x in xs if x is not None]
    if not xs:
        parts.append(f'<line x1="{margin}" y1="{base}" x2="{W - margin}" y2="{base}" class="p-line flat"/>')
        parts.append(f'<text x="{W / 2}" y="{base - 12}" text-anchor="middle" class="p-noise">\u2014 AWAITING SIGNAL \u2014</text>')
    else:
        path = [f"M {margin} {base}"]
        for x in sorted(xs):
            path.append(f"L {x - 16:.1f} {base}")
            path.append(f"L {x - 7:.1f} {base + 7}")
            path.append(f"L {x:.1f} {base - 52}")
            path.append(f"L {x + 4:.1f} {base + 12}")
            path.append(f"L {x + 10:.1f} {base - 4}")
            path.append(f"L {x + 16:.1f} {base}")
        path.append(f"L {W - margin:.1f} {base}")
        parts.append(f'<path d="{" ".join(path)}" class="p-line" fill="none"/>')
        for x in xs:
            parts.append(f'<circle cx="{x:.1f}" cy="{base - 52}" r="3" class="p-dot"/>')
    parts.append(f'<line class="p-sweep" x1="{margin}" y1="24" x2="{margin}" y2="{H - 20}"/>')
    parts.append("</svg>")
    return "".join(parts)


def generate_dashboard_html() -> str:
    """Generate the full HTML dashboard."""
    status = get_system_status()

    drive = float(status.get("drive_score", 0.0) or 0.0)
    ambition = float(status.get("ambition_level", 0.5) or 0.5)
    gap = float(status.get("gap", 0.0) or 0.0)

    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%d %H:%M UTC")
    hb = (status.get("spawn", {}) or {}).get("last_heartbeat")
    state_label, state_cls = _freshness(hb)

    gauge = _gauge_svg(drive)

    events = []
    for a in status.get("recent_actions", []) or []:
        dt = _parse_dt(a.get("timestamp"))
        if dt is not None:
            events.append(dt)
    pulse = _pulse_svg(events)

    total_articles = int(status.get("total_articles", 0) or 0)
    total_niches = int(status.get("total_niches", 0) or 0)
    apw = float(status.get("articles_per_week", 0.0) or 0.0)
    profit = float(status.get("total_profit", 0.0) or 0.0)
    revenue = float(status.get("total_revenue", 0.0) or 0.0)
    roi = float(status.get("roi", 0.0) or 0.0)
    clicks = int(status.get("total_clicks", 0) or 0)
    aff = int(status.get("affiliate_clicks", 0) or 0)
    queue = int(status.get("queue_size", 0) or 0)
    days_flat = int(status.get("days_flat", 0) or 0)
    last_action = status.get("last_action", "None")

    vitals = [
        dict(label="Surplus", value=f"${profit:,.2f}", state="alive",
             sub=f"${revenue:,.2f} revenue \u00b7 {roi:.2f}x ROI"),
        dict(label="Content", value=f"{total_niches}", state="default",
             sub=f"{total_articles} articles \u00b7 {apw:.1f}/wk"),
        dict(label="Engagement", value=f"{clicks}", state="default",
             sub=f"{aff} affiliate clicks"),
        dict(label="Backlog", value=f"{queue}", state="default",
             sub=f"{days_flat} days flat \u00b7 {last_action}"),
    ]
    vitals_html = ""
    for v in vitals:
        vitals_html += f"""
        <div class="vital panel">
            <span class="eyebrow">{v['label']}</span>
            <span class="vital-value {v['state']}">{v['value']}</span>
            <span class="vital-sub mono">{v['sub']}</span>
        </div>"""

    win = status.get("win", {}) or {}
    fable = status.get("fable", {}) or {}
    memory = status.get("memory", {}) or {}
    spawn = status.get("spawn", {}) or {}
    lineage = status.get("lineage", {}) or {}
    unified = status.get("unified", {}) or {}
    brain = status.get("brain", {}) or {}
    gsc = status.get("gsc", {}) or {}
    cortex = status.get("cortex", {}) or {}
    n8n = status.get("n8n", {}) or {}

    organs = [
        dict(tag="WIN", name="win.sh loops",
             state=_organ_state(win.get("total_runs"), win.get("active_loops")),
             rows=[("Active loops", win.get("active_loops", 0)),
                   ("Total runs", win.get("total_runs", 0)),
                   ("Outcomes", win.get("total_outcomes", 0)),
                   ("Completed", win.get("total_completed", 0))]),
        dict(tag="FABLE", name="Fable method",
             state=_organ_state(fable.get("total_plans"), 0),
             rows=[("Plans", fable.get("total_plans", 0)),
                   ("Verifications", fable.get("total_verifications", 0)),
                   ("Learnings", fable.get("total_learnings", 0)),
                   ("Last cycle", _fmt_utc(fable.get("last_cycle")))]),
        dict(tag="MEM", name="Neural memory",
             state=_organ_state(memory.get("entities"), 0),
             rows=[("Entities", memory.get("entities", 0)),
                   ("Relationships", memory.get("relationships", 0)),
                   ("Insights", memory.get("insights", 0)),
                   ("Ingested", _fmt_utc(memory.get("last_ingestion")))]),
        dict(tag="SPN", name="Core spawning",
             state=_organ_state(0, int(spawn.get("followers", 0) or 0)),
             rows=[("Role", spawn.get("role", "\u2014")),
                   ("Followers", int(spawn.get("followers", 0) or 0)),
                   ("Heartbeat", _fmt_utc(spawn.get("last_heartbeat"))),
                   ("Leader", str(spawn.get("leader", "None"))[:22])]),
        dict(tag="GEN", name="Genesis lineage",
             state=_organ_state(0, lineage.get("generations")),
             rows=[("Version", f"V{lineage.get('current_version', 1)}"),
                   ("Generations", lineage.get("generations", 0)),
                   ("Transfer", _fmt_utc(lineage.get("last_transfer"))),
                   ("Last death", _fmt_utc(lineage.get("last_death")))]),
        dict(tag="UDB", name="Unified database",
             state=_organ_state(unified.get("total_subscribers"), 0),
             rows=[("Subscribers", unified.get("total_subscribers", 0)),
                   ("Active alerts", unified.get("active_alerts", 0)),
                   ("Campaigns", unified.get("total_campaigns", 0)),
                   ("Profit", f"${float(unified.get('total_profit', 0) or 0):,.2f}")]),
        dict(tag="BRN", name="Brain library",
             state=_organ_state(brain.get("books"), 0),
             rows=[("Books", brain.get("books", 0)),
                   ("Categories", brain.get("categories", 0)),
                   ("Entities", brain.get("entities", 0)),
                   ("Status", brain.get("status", "\u2014"))]),
        dict(tag="GSC", name="Google Search Console",
             state=_organ_state(gsc.get("total_clicks"), 0),
             rows=[("Clicks", gsc.get("total_clicks", 0)),
                   ("Impressions", gsc.get("total_impressions", 0)),
                   ("Avg CTR", f"{float(gsc.get('avg_ctr', 0) or 0):.2%}"),
                   ("Avg position", f"{float(gsc.get('avg_position', 0) or 0):.1f}")]),
        dict(tag="CTX", name="Symbiotic Cortex",
             state="alive" if cortex.get("watching") else ("armed" if cortex.get("enabled") else "idle"),
             rows=[("Status", "Active" if cortex.get("watching") else ("Enabled" if cortex.get("enabled") else "Disabled")),
                   ("Corrections", cortex.get("corrections_logged", 0)),
                   ("Vault", str(cortex.get("vault") or "Not set")[:26]),
                   ("Journals", len(cortex.get("recent_entries", []) or []))]),
        dict(tag="N8N", name="n8n automation",
             state="alive" if n8n.get("healthy") else ("armed" if n8n.get("status") == "error" else "idle"),
             rows=[("Status", "Connected" if n8n.get("healthy") else ("Unreachable" if n8n.get("status") == "error" else "Idle")),
                   ("Endpoint", str(n8n.get("n8n_url") or "Not set")[:26]),
                   ("Bridge", "abvorn/core/n8n_bridge.py"),
                   ("Webhooks", "/webhook/abvorn/{action}")]),
    ]
    organs_html = ""
    for o in organs:
        rows = "".join(
            f'<div class="row"><span class="row-label">{r[0]}</span><span class="row-value mono">{r[1]}</span></div>'
            for r in o["rows"]
        )
        organs_html += f"""
        <div class="organ">
            <div class="organ-head">
                <span class="organ-tag mono">{o['tag']}</span>
                <span class="organ-name">{o['name']}</span>
                <span class="lamp-dot {o['state']}" title="{o['state']}"></span>
            </div>
            <div class="organ-rows">{rows}</div>
        </div>"""

    weights = status.get("verdict_weights", {}) or {}
    if weights:
        w_items = []
        for cat, w in weights.items():
            try:
                pct = float(w) * 100
            except (TypeError, ValueError):
                continue
            w_items.append(f"""
            <div class="weight-row">
                <span class="weight-label">{cat}</span>
                <div class="weight-track"><div class="weight-fill" style="width:{pct:.0f}%"></div></div>
                <span class="weight-value mono">{pct:.0f}%</span>
            </div>""")
        weights_html = "".join(w_items)
    else:
        weights_html = '<div class="empty">Awaiting first verdict \u2014 weights calibrate once reviews pass the gate.</div>'

    actions = status.get("recent_actions", []) or []
    if actions:
        a_items = []
        for a in actions[:8]:
            ts = _fmt_utc(a.get("timestamp"))
            name = a.get("action", "action")
            result = str(a.get("result", ""))[:70] or str(a.get("gap", ""))
            verified = a.get("verified")
            mark = "\u2713" if verified else "\u00b7"
            a_items.append(f"""
            <div class="log-row">
                <span class="log-time mono">{ts}</span>
                <span class="log-name">{name}</span>
                <span class="log-result">{result}</span>
                <span class="log-mark {'ok' if verified else ''}">{mark}</span>
            </div>""")
        actions_html = "".join(a_items)
    else:
        actions_html = '<div class="empty">No actions recorded yet \u2014 the machine is idle.</div>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Abvorn Console</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
{_CONSOLE_CSS}
</style>
</head>
<body>
<div class="shell">
  <header class="topbar">
    <div class="brand"><span class="brand-dot"></span><span class="brand-word">ABVORN</span><span class="brand-sub">// CONSOLE</span></div>
    <div class="topbar-right">
      <span class="lamp {state_cls}"><i class="lamp-bulb"></i>{state_label}</span>
      <span class="clock mono">{now}</span>
    </div>
  </header>

  <section class="pulse panel" aria-label="System activity signal, last 7 days">
    <div class="pulse-head">
      <span class="eyebrow">Signal \u00b7 last 7 days</span>
      <span class="pulse-meta mono">{len(events)} events</span>
    </div>
    {pulse}
    <div class="pulse-foot mono">time \u2192 activity \u00a0\u00b7\u00a0 spike = verified action</div>
  </section>

  <main class="main-grid">
    <section class="gauge-panel panel" aria-label="Drive score">
      <span class="eyebrow">Drive Score</span>
      {gauge}
      <div class="gauge-readouts">
        <div class="readout"><span class="readout-value mono">{drive:.3f}</span><span class="readout-label">score</span></div>
        <div class="readout"><span class="readout-value mono">{gap:.3f}</span><span class="readout-label">gap to goal</span></div>
      </div>
      <div class="ambition">
        <span class="ambition-label mono">ambition {ambition:.2f}</span>
        <div class="ambition-track"><div class="ambition-fill" style="width:{ambition * 100:.0f}%"></div></div>
      </div>
    </section>

    <div class="vitals-grid">
      {vitals_html}
    </div>
  </main>

  <section class="panel organs" aria-label="Subsystems">
    <span class="eyebrow">Subsystems</span>
    <div class="organ-grid">
      {organs_html}
    </div>
  </section>

  <div class="bottom-grid">
    <section class="panel" aria-label="Verdict weights">
      <span class="eyebrow">Verdict Weights</span>
      {weights_html}
    </section>
    <section class="panel" aria-label="Recent actions">
      <span class="eyebrow">Recent Actions</span>
      <div class="log">
        {actions_html}
      </div>
    </section>
  </div>

  <footer class="foot mono">live \u00b7 auto-refresh 30s \u00a0\u00b7\u00a0 abvorn.com</footer>
</div>
<script>
(function () {{
  const API = '/api/dashboard/metrics';
  const INTERVAL = 30000;

  function $(sel) {{ return document.querySelector(sel); }}

  function updateClock() {{
    var el = $('.clock');
    if (el) el.textContent = new Date().toISOString().replace('T',' ').slice(0,19) + ' UTC';
  }}

  function updateVitals(d) {{
    var profit = parseFloat(d.total_profit || 0);
    var revenue = parseFloat(d.total_revenue || 0);
    var roi = parseFloat(d.roi || 0);
    var niches = parseInt(d.total_niches || 0);
    var articles = parseInt(d.total_articles || 0);
    var apw = parseFloat(d.articles_per_week || 0);
    var clicks = parseInt(d.total_clicks || 0);
    var aff = parseInt(d.affiliate_clicks || 0);
    var queue = parseInt(d.queue_size || 0);
    var days = parseInt(d.days_flat || 0);
    var last = d.last_action || 'None';
    var vitals = document.querySelectorAll('.vital');
    if (vitals.length >= 4) {{
      vitals[0].querySelector('.vital-value').textContent = '$' + profit.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}});
      vitals[0].querySelector('.vital-sub').textContent = '$' + revenue.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}}) + ' revenue \u00b7 ' + roi.toFixed(2) + 'x ROI';
      vitals[1].querySelector('.vital-value').textContent = niches;
      vitals[1].querySelector('.vital-sub').textContent = articles + ' articles \u00b7 ' + apw.toFixed(1) + '/wk';
      vitals[2].querySelector('.vital-value').textContent = clicks;
      vitals[2].querySelector('.vital-sub').textContent = aff + ' affiliate clicks';
      vitals[3].querySelector('.vital-value').textContent = queue;
      vitals[3].querySelector('.vital-sub').textContent = days + ' days flat \u00b7 ' + last;
    }}
  }}

  function updateOrgans(d) {{
    var organs = document.querySelectorAll('.organ');
    var sources = [d.win, d.fable, d.memory, d.spawn, d.lineage, d.unified, d.brain, d.gsc, d.cortex, d.n8n];
    organs.forEach(function (org, i) {{
      if (i >= sources.length) return;
      var s = sources[i] || {{}};
      var rows = org.querySelectorAll('.row');
      var keys = Object.keys(s).filter(function(k) {{ return typeof s[k] !== 'object'; }});
      rows.forEach(function (row, j) {{
        if (j < keys.length) {{
          var val = s[keys[j]];
          var rv = row.querySelector('.row-value');
          if (rv) rv.textContent = typeof val === 'number' ? val.toLocaleString() : (val || '\u2014');
        }}
      }});
    }});
  }}

  function updateGauge(d) {{
    var drive = parseFloat(d.drive_score || 0);
    var gap = parseFloat(d.gap || 0);
    var ambition = parseFloat(d.ambition_level || 0.5);
    var readouts = document.querySelectorAll('.readout-value');
    if (readouts.length >= 2) {{
      readouts[0].textContent = drive.toFixed(3);
      readouts[1].textContent = gap.toFixed(3);
    }}
    var ab = document.querySelector('.ambition-label');
    if (ab) ab.textContent = 'ambition ' + ambition.toFixed(2);
    var af = document.querySelector('.ambition-fill');
    if (af) af.style.width = (ambition * 100) + '%';
    var label = document.querySelector('.lamp');
    if (label) {{
      label.className = 'lamp ' + (d.status === 'active' ? 'alive' : (d.status === 'armed' ? 'armed' : 'idle'));
    }}
  }}

  function refresh() {{
    fetch(API).then(function(r) {{ return r.json(); }}).then(function(d) {{
      updateVitals(d);
      updateOrgans(d);
      updateGauge(d);
      updateClock();
    }}).catch(function() {{}});
  }}

  setInterval(refresh, INTERVAL);
  setInterval(updateClock, 1000);
}})();
</script>
</body>
</html>
    """
    return html



def generate_and_write_dashboard() -> str:
    """Generate the dashboard and write it to docs/console.html."""
    html = generate_dashboard_html()
    output_path = PROJECT_DIR / "docs" / "console.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info(f"Dashboard written to {output_path}")
    return str(output_path)


if __name__ == "__main__":
    print(generate_and_write_dashboard())
