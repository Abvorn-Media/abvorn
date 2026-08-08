"""console_dashboard.py — Abvorn Console dashboard generator.

Reads all real data sources and renders a self-contained HTML page
(and a JSON snapshot) for the command center.
"""

import json
import logging
import sqlite3
from datetime import datetime
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
    return {
        "drive_score": float(data.get("drive_score", 0.0) or 0.0),
        "ambition_level": float(data.get("ambition_level", 0.5) or 0.5),
        "last_action": data.get("action", data.get("last_action", "None")),
        "status": data.get("status", "unknown"),
        "days_flat": int(data.get("days_flat", 0) or 0),
        "recent_actions": history[-5:],
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
    }


def generate_dashboard_html() -> str:
    """Generate the full HTML dashboard."""
    status = get_system_status()

    recent_actions_html = ""
    for action in status.get("recent_actions", []):
        ts = str(action.get("timestamp", ""))[:19]
        name = action.get("action", "unknown")
        result = str(action.get("result", action.get("gap", "")))[:80]
        recent_actions_html += f"""
        <div class="action-item">
            <span class="action-time">{ts}</span>
            <span class="action-name">{name}</span>
            <span class="action-result">{result}</span>
        </div>
        """

    weights_html = ""
    for category, weight in status.get("verdict_weights", {}).items():
        try:
            percent = float(weight) * 100
        except (TypeError, ValueError):
            continue
        weights_html += f"""
        <div class="weight-item">
            <span class="weight-label">{category}</span>
            <div class="weight-bar">
                <div class="weight-fill" style="width: {percent:.0f}%;"></div>
            </div>
            <span class="weight-value">{percent:.0f}%</span>
        </div>
        """

    win = status.get("win", {})
    win_html = f"""
    <div class="win-grid">
        <div class="win-item"><span class="win-label">Active Loops</span><span class="win-value">{win.get("active_loops", 0)}</span></div>
        <div class="win-item"><span class="win-label">Total Runs</span><span class="win-value">{win.get("total_runs", 0)}</span></div>
        <div class="win-item"><span class="win-label">Outcomes</span><span class="win-value">{win.get("total_outcomes", 0)}</span></div>
        <div class="win-item"><span class="win-label">Completed</span><span class="win-value">{win.get("total_completed", 0)}</span></div>
    </div>
    """

    fable = status.get("fable", {})
    fable_html = f"""
    <div class="fable-grid">
        <div class="fable-item"><span class="fable-label">Plans</span><span class="fable-value">{fable.get("total_plans", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">Verifications</span><span class="fable-value">{fable.get("total_verifications", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">Learnings</span><span class="fable-value">{fable.get("total_learnings", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">Last Cycle</span><span class="fable-value">{str(fable.get("last_cycle", "Never"))[:19]}</span></div>
    </div>
    """

    memory = status.get("memory", {})
    memory_html = f"""
    <div class="fable-grid">
        <div class="fable-item"><span class="fable-label">Entities</span><span class="fable-value">{memory.get("entities", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">Relationships</span><span class="fable-value">{memory.get("relationships", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">Insights</span><span class="fable-value">{memory.get("insights", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">Ingested</span><span class="fable-value">{str(memory.get("last_ingestion", "Never"))[:19]}</span></div>
    </div>
    """

    spawn = status.get("spawn", {})
    spawn_html = f"""
    <div class="fable-grid">
        <div class="fable-item"><span class="fable-label">Role</span><span class="fable-value">{spawn.get("role", "awaiting_leader")}</span></div>
        <div class="fable-item"><span class="fable-label">Followers</span><span class="fable-value">{spawn.get("followers", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">Heartbeat</span><span class="fable-value">{str(spawn.get("last_heartbeat", "Never"))[:19]}</span></div>
        <div class="fable-item"><span class="fable-label">Leader</span><span class="fable-value" style="max-width:150px;overflow:hidden;text-overflow:ellipsis;">{spawn.get("leader", "None")}</span></div>
    </div>
    """

    lineage = status.get("lineage", {})
    lineage_html = f"""
    <div class="fable-grid">
        <div class="fable-item"><span class="fable-label">Version</span><span class="fable-value">V{lineage.get("current_version", 1)}</span></div>
        <div class="fable-item"><span class="fable-label">Generations</span><span class="fable-value">{lineage.get("generations", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">Last Transfer</span><span class="fable-value">{str(lineage.get("last_transfer", "Never"))[:19]}</span></div>
        <div class="fable-item"><span class="fable-label">Last Death</span><span class="fable-value">{str(lineage.get("last_death", "Never"))[:19]}</span></div>
    </div>
    """

    unified = status.get("unified", {})
    unified_html = f"""
    <div class="fable-grid">
        <div class="fable-item"><span class="fable-label">Subscribers</span><span class="fable-value">{unified.get("total_subscribers", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">Active Alerts</span><span class="fable-value">{unified.get("active_alerts", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">Campaigns</span><span class="fable-value">{unified.get("total_campaigns", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">DB Profit</span><span class="fable-value">${unified.get("total_profit", 0):.2f}</span></div>
    </div>
    """

    brain = status.get("brain", {})
    brain_html = f"""
    <div class="fable-grid">
        <div class="fable-item"><span class="fable-label">Books</span><span class="fable-value">{brain.get("books", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">Categories</span><span class="fable-value">{brain.get("categories", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">Entities</span><span class="fable-value">{brain.get("entities", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">Status</span><span class="fable-value">{brain.get("status", "unavailable")}</span></div>
    </div>
    """

    gsc = status.get("gsc", {})
    gsc_html = f"""
    <div class="fable-grid">
        <div class="fable-item"><span class="fable-label">Clicks</span><span class="fable-value">{gsc.get("total_clicks", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">Impressions</span><span class="fable-value">{gsc.get("total_impressions", 0)}</span></div>
        <div class="fable-item"><span class="fable-label">Avg CTR</span><span class="fable-value">{gsc.get("avg_ctr", 0):.2%}</span></div>
        <div class="fable-item"><span class="fable-label">Avg Position</span><span class="fable-value">{gsc.get("avg_position", 0):.1f}</span></div>
        <div class="fable-item"><span class="fable-label">Window</span><span class="fable-value">{gsc.get("days", 0)}d</span></div>
        <div class="fable-item"><span class="fable-label">Last Ingest</span><span class="fable-value">{str(gsc.get("last_ingestion", "Never"))[:16]}</span></div>
    </div>
    """

    cortex = status.get("cortex", {})
    cortex_recent_html = ""
    for entry in cortex.get("recent_entries", [])[:3]:
        name = entry.get("file", "")
        modified = str(entry.get("modified", ""))[:16]
        preview = str(entry.get("preview", ""))[:80].replace("\n", " ")
        cortex_recent_html += (
            f'<div class="cortex-entry"><strong>{name}</strong> '
            f'<span style="color:var(--text-dim);font-size:12px;">{modified}</span>'
            f'<div style="font-size:12px;color:var(--text-dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{preview}</div></div>'
        )
    cortex_status_txt = "Active" if cortex.get("watching") else ("Enabled" if cortex.get("enabled") else "Disabled")
    cortex_html = f"""
    <div class="fable-grid">
        <div class="fable-item"><span class="fable-label">Status</span><span class="fable-value">{cortex_status_txt}</span></div>
        <div class="fable-item"><span class="fable-label">Corrections</span><span class="fable-value">{cortex.get("corrections_logged", 0)}</span></div>
        <div class="fable-item" style="grid-column: 1 / -1;">
            <span class="fable-label">Vault</span>
            <span class="fable-value" style="font-size:12px;word-break:break-all;">{cortex.get("vault") or "Not set"}</span>
        </div>
        <div class="fable-item" style="grid-column: 1 / -1;">
            <span class="fable-label">Recent Journal</span>
            <div style="grid-column:1/-1;">{cortex_recent_html or '<span style="color:var(--text-dim);font-size:12px;">No entries yet</span>'}</div>
        </div>
    </div>
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Abvorn Console</title>
    <style>
        :root {{
            --bg: #0a0a0a;
            --card: #1a1a1a;
            --border: #2a2a2a;
            --accent: #c98a2c;
            --text: #e0e0e0;
            --text-dim: #888;
            --radius: 8px;
            --shadow: 0 4px 20px rgba(0,0,0,0.4);
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 20px;
        }}
        .logo {{
            font-size: 24px;
            font-weight: 700;
            color: var(--accent);
        }}
        .logo span {{ color: var(--text); }}
        .timestamp {{
            font-size: 14px;
            color: var(--text-dim);
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 20px;
            box-shadow: var(--shadow);
        }}
        .card-title {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-dim);
            margin-bottom: 12px;
        }}
        .card-value {{
            font-size: 32px;
            font-weight: 700;
            color: var(--text);
        }}
        .card-value.gold {{ color: var(--accent); }}
        .card-value.green {{ color: #4caf50; }}
        .card-value.red {{ color: #e74c3c; }}
        .card-sub {{
            font-size: 14px;
            color: var(--text-dim);
            margin-top: 4px;
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 16px;
            color: var(--text);
        }}

        .weight-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 8px;
        }}
        .weight-label {{
            width: 80px;
            font-size: 14px;
            color: var(--text-dim);
        }}
        .weight-bar {{
            flex: 1;
            height: 6px;
            background: var(--border);
            border-radius: 3px;
            overflow: hidden;
        }}
        .weight-fill {{
            height: 100%;
            background: var(--accent);
            border-radius: 3px;
            transition: width 0.3s;
        }}
        .weight-value {{
            width: 50px;
            text-align: right;
            font-size: 14px;
            color: var(--text);
        }}

        .action-item {{
            display: flex;
            gap: 16px;
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
            font-size: 14px;
        }}
        .action-item:last-child {{ border-bottom: none; }}
        .action-time {{
            color: var(--text-dim);
            width: 100px;
            flex-shrink: 0;
        }}
        .action-name {{
            font-weight: 600;
            min-width: 120px;
        }}
        .action-result {{
            color: var(--text-dim);
        }}

        .win-grid, .fable-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px 12px;
        }}
        .win-item, .fable-item {{
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            border-bottom: 1px solid var(--border);
        }}
        .win-label, .fable-label {{
            color: var(--text-dim);
        }}
        .win-value, .fable-value {{
            font-weight: 600;
        }}
        .two-col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        @media (max-width: 768px) {{
            .two-col {{ grid-template-columns: 1fr; }}
            .win-grid, .fable-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <div class="logo">Abvorn <span>Console</span></div>
        <div class="timestamp">Last updated: {status.get('timestamp', datetime.now().isoformat())[:19]}</div>
    </header>

    <!-- Stats Grid -->
    <div class="grid">
        <div class="card">
            <div class="card-title">Drive Score</div>
            <div class="card-value gold">{status.get('drive_score', 0):.3f}</div>
            <div class="card-sub">Ambition: {status.get('ambition_level', 0.5):.2f} / 1.0</div>
        </div>
        <div class="card">
            <div class="card-title">Economic Surplus</div>
            <div class="card-value green">${status.get('total_profit', 0):.2f}</div>
            <div class="card-sub">Revenue: ${status.get('total_revenue', 0):.2f} · ROI: {status.get('roi', 0):.2f}x</div>
        </div>
        <div class="card">
            <div class="card-title">Content</div>
            <div class="card-value">{status.get('total_niches', 0)}</div>
            <div class="card-sub">{status.get('total_articles', 0)} articles · {status.get('articles_per_week', 0):.1f}/week</div>
        </div>
        <div class="card">
            <div class="card-title">Engagement</div>
            <div class="card-value">{status.get('total_clicks', 0)}</div>
            <div class="card-sub">Total clicks · {status.get('affiliate_clicks', 0)} affiliate</div>
        </div>
        <div class="card">
            <div class="card-title">Status</div>
            <div class="card-value">
                {status.get('queue_size', 0)} queued
                <span style="font-size:16px;font-weight:400;color:var(--text-dim);margin-left:8px;">
                    {status.get('days_flat', 0)} days flat
                </span>
            </div>
            <div class="card-sub">Last action: {status.get('last_action', 'None')}</div>
        </div>
        <div class="card">
            <div class="card-title">win.sh</div>
            {win_html}
        </div>
        <div class="card">
            <div class="card-title">Fable Method</div>
            {fable_html}
        </div>
        <div class="card">
            <div class="card-title">Neural Memory</div>
            {memory_html}
        </div>
        <div class="card">
            <div class="card-title">Core Spawning</div>
            {spawn_html}
        </div>
        <div class="card">
            <div class="card-title">Genesis Lineage</div>
            {lineage_html}
        </div>
        <div class="card">
            <div class="card-title">Unified Database</div>
            {unified_html}
        </div>
        <div class="card">
            <div class="card-title">Brain Library</div>
            {brain_html}
        </div>
        <div class="card">
            <div class="card-title">Google Search Console</div>
            {gsc_html}
        </div>
        <div class="card">
            <div class="card-title">Symbiotic Cortex</div>
            {cortex_html}
        </div>
    </div>

    <!-- Two Columns: Verdict Weights + Recent Actions -->
    <div class="two-col">
        <div class="card">
            <div class="card-title">Verdict Weights</div>
            {weights_html or '<div style="color:var(--text-dim);">No weights loaded yet</div>'}
        </div>
        <div class="card">
            <div class="card-title">Recent Actions</div>
            {recent_actions_html or '<div style="color:var(--text-dim);">No actions recorded</div>'}
        </div>
    </div>
</div>
<script>
    setTimeout(() => location.reload(), 60000);
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
