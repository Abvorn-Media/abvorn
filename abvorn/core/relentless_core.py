"""relentless_core.py — The Relentless Core of Abvorn.

Measures real performance, identifies gaps, and proposes safe actions.
No simulations. No fake APIs. Driven by actual data.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_STATE_PATH = Path("data/relentless_state.json")
_CLICKS_DB = Path("data/clicks.db")
_CYCLE_STATE = Path("cycle_state.json")
_WEIGHTS_PATH = Path("data/verdict_weights.json")
_PRICE_DB = Path("data/price_history.db")

_ACTIONS = [
    "expand_content_velocity",
    "refine_quality",
    "format_shift",
    "content_structure",
    "platform_expansion",
    "social_scheduling",
    "email_newsletter",
    "monetization",
    "dynamic_affiliate_optimization",
    "user_engagement",
    "personalization",
    "price_alerts",
    "data_source_innovation",
    "api_development",
]


def _load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _read_engagement() -> float:
    try:
        if not _CLICKS_DB.exists():
            return 0.0
        con = sqlite3.connect(_CLICKS_DB)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM clicks")
        clicks = cur.fetchone()[0]
        con.close()
        return min(clicks / 100, 1.0)
    except Exception:
        return 0.0


def _read_velocity() -> float:
    try:
        data = _load_json(_CYCLE_STATE, {})
        deployed = data.get("deployed", [])
        return len(deployed) / 4.0
    except Exception:
        return 0.0


def _read_adaptation() -> float:
    try:
        data = _load_json(_WEIGHTS_PATH, {})
        overrides = data.get("abvorn", {})
        return min(len(overrides) / 10.0, 1.0)
    except Exception:
        return 0.0


def _read_economic_surplus() -> float:
    try:
        if not _PRICE_DB.exists():
            return 0.0
        con = sqlite3.connect(_PRICE_DB)
        cur = con.cursor()
        cur.execute("SELECT COUNT(DISTINCT product_id) FROM price_history")
        products = cur.fetchone()[0]
        con.close()
        return float(products) * 10.0
    except Exception:
        return 0.0


def _calculate_drive_score(metrics: Dict[str, float], ambition: float) -> float:
    return (
        0.30 * min(metrics["economic_surplus"] / 100, 1.0)
        + 0.25 * metrics["user_engagement"]
        + 0.20 * min(metrics["content_velocity"] / 10, 1.0)
        + 0.15 * metrics["adaptation_rate"]
        + 0.10 * ambition
    )


def _plan_action(gap: float, metrics: Dict[str, float]) -> str:
    if gap > 0.35:
        if metrics["content_velocity"] < 2:
            return "expand_content_velocity"
        return "platform_expansion"
    if gap > 0.20:
        if metrics["adaptation_rate"] < 0.3:
            return "data_source_innovation"
        return "dynamic_affiliate_optimization"
    if gap > 0.10:
        return "user_engagement"
    return "refine_quality"


def cycle_relentless_core() -> Dict[str, Any]:
    """Run one relentless drive cycle."""
    state = _load_json(_STATE_PATH, {})

    metrics = {
        "economic_surplus": _read_economic_surplus(),
        "user_engagement": _read_engagement(),
        "content_velocity": _read_velocity(),
        "adaptation_rate": _read_adaptation(),
    }
    ambition = float(state.get("ambition_level", 0.5))
    drive_score = _calculate_drive_score(metrics, ambition)

    target = {
        "economic_surplus": ambition * 100,
        "user_engagement": ambition * 0.9,
        "content_velocity": ambition * 10,
        "adaptation_rate": ambition * 0.8,
    }
    gap = sum(
        max(0.0, target[k] - metrics[k]) / max(target[k], 1.0)
        for k in target
    ) / len(target)

    action = "refine_quality"
    if gap > 0.05:
        action = _plan_action(gap, metrics)

    result = {
        "timestamp": datetime.now().isoformat(),
        "metrics": metrics,
        "drive_score": round(drive_score, 4),
        "gap": round(gap, 4),
        "action": action,
        "status": "executed",
        "ambition_level": round(ambition, 2),
        "history": state.get("history", [])[-50:],
    }
    result["history"].append({
        "timestamp": result["timestamp"],
        "drive_score": result["drive_score"],
        "action": action,
        "gap": result["gap"],
    })

    state.update(result)
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STATE_PATH.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    except Exception as e:
        logger.warning("Relentless state save failed: %s", e)

    logger.info(
        "RelentlessCore cycle: drive=%.4f gap=%.4f action=%s ambition=%.2f",
        drive_score, gap, action, ambition,
    )
    return result


def get_relentless_status() -> Dict[str, Any]:
    """Return current status for dashboards."""
    state = _load_json(_STATE_PATH, {})
    return {
        "ambition_level": state.get("ambition_level", 0.5),
        "drive_score": state.get("drive_score", 0.0),
        "gap": state.get("gap", 1.0),
        "current_action": state.get("action", "none"),
        "metrics": state.get("metrics", {}),
        "total_cycles": len(state.get("history", [])),
        "last_cycle": state.get("timestamp", ""),
    }
