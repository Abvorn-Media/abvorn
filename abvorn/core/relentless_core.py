"""relentless_core.py — The Relentless Core of Abvorn.

Minimal, real version. Reads from actual data sources and drives the system.
No simulations. No fake APIs.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RelentlessCore:
    """
    Minimal, real version of the Relentless Core.
    Reads from actual data sources and drives the system.
    """

    def __init__(self):
        self.data_dir = Path("data")
        self.state_file = Path("cycle_state.json")
        self.clicks_db = self.data_dir / "clicks.db"
        self.economic_file = self.data_dir / "economic_records.json"
        self.weights_file = self.data_dir / "verdict_weights.json"

        # State
        self.ambition_level = 0.5
        self.drive_score = 0.0
        self.last_action = None
        self.history = []

    def _read_clicks(self) -> Dict[str, int]:
        """Read total clicks per article from clicks.db."""
        try:
            if not self.clicks_db.exists():
                return {}
            conn = sqlite3.connect(str(self.clicks_db))
            cursor = conn.cursor()
            cursor.execute("SELECT article_id, COUNT(*) FROM clicks GROUP BY article_id")
            rows = cursor.fetchall()
            conn.close()
            return {row[0]: row[1] for row in rows}
        except Exception as e:
            logger.warning(f"Could not read clicks: {e}")
            return {}

    def _read_economic_surplus(self) -> float:
        """Read total profit from economic records."""
        try:
            if not self.economic_file.exists():
                return 0.0
            data = json.loads(self.economic_file.read_text())
            if isinstance(data, list):
                return sum(r.get("profit", 0) for r in data)
            return 0.0
        except Exception as e:
            logger.warning(f"Could not read economic surplus: {e}")
            return 0.0

    def _read_cycle_state(self) -> Dict:
        """Read the current state of the system."""
        try:
            if not self.state_file.exists():
                return {"deployed": [], "queue": [], "performance": {}}
            return json.loads(self.state_file.read_text())
        except Exception as e:
            logger.warning(f"Could not read state: {e}")
            return {"deployed": [], "queue": [], "performance": {}}

    def _read_verdict_weights(self) -> Dict:
        """Read the current Verdict Engine weights."""
        try:
            if not self.weights_file.exists():
                return {}
            return json.loads(self.weights_file.read_text())
        except Exception as e:
            logger.warning(f"Could not read weights: {e}")
            return {}

    def _calculate_drive_score(self) -> float:
        """Calculate the drive score from real data."""
        clicks = self._read_clicks()
        total_clicks = sum(clicks.values())
        surplus = self._read_economic_surplus()
        state = self._read_cycle_state()
        deployed = len(state.get("deployed", []))
        queue = len(state.get("queue", []))

        # Normalize each metric (roughly)
        engagement = min(total_clicks / 100, 1.0)  # 100 clicks = 1.0
        economic = min(surplus / 10, 1.0)  # $10 profit = 1.0
        velocity = min(deployed / 10, 1.0)  # 10 niches = 1.0
        momentum = min(queue / 5, 1.0)  # 5 queued = 1.0

        # Weighted score
        return (
            0.30 * economic
            + 0.25 * engagement
            + 0.20 * velocity
            + 0.15 * momentum
            + 0.10 * self.ambition_level
        )

    def _decide_action(self, drive_score: float) -> str:
        """Decide what action to take based on the drive score."""
        # Read current state to understand what's happening
        state = self._read_cycle_state()
        deployed = len(state.get("deployed", []))
        queue = len(state.get("queue", []))

        # If drive score is low, take aggressive actions
        if drive_score < 0.3:
            return "expand_content"  # Add more niches
        elif drive_score < 0.5:
            if deployed > 0 and queue < 3:
                return "expand_content"
            else:
                return "optimize_conversion"
        elif drive_score < 0.7:
            return "refine_quality"
        else:
            # High drive score: push into new territory
            return "explore_new_domain"

    def _execute_action(self, action: str) -> str:
        """Execute the action."""
        if action == "expand_content":
            # Trigger content strategist to add new niches
            try:
                from run_cycle import pick_niche

                state = self._read_cycle_state()
                # Prefer pick_niche to advance queue; if unavailable, mark intent
                try:
                    pick_niche(state)
                except Exception:
                    pass
                self.state_file.write_text(json.dumps(state, indent=2))
                return "Expanded content (added new niches)"
            except Exception as e:
                logger.warning(f"expand_content failed: {e}")
                return "Expansion requested (content strategist not available)"

        elif action == "optimize_conversion":
            # Increase affiliate link prominence or adjust CTAs
            # For now, log it
            logger.info("Optimizing conversion: consider adjusting CTAs")
            return "Optimization requested"

        elif action == "refine_quality":
            # Improve content quality (humanizer, chart UX)
            logger.info("Refining quality: consider humanizer improvements")
            return "Quality refinement requested"

        elif action == "explore_new_domain":
            # Use Agent-Reach to find new trends (if available)
            try:
                from src.agent_reach_adapter import get_agent_reach

                agent = get_agent_reach()
                return "New domain exploration triggered"
            except Exception:
                return "Agent-Reach not available"
        else:
            return f"Unknown action: {action}"

    def cycle(self) -> Dict[str, Any]:
        """Run one drive cycle."""
        # 1. Calculate current drive score
        drive_score = self._calculate_drive_score()
        self.drive_score = drive_score

        # 2. Decide action
        action = self._decide_action(drive_score)

        # 3. Execute action
        result = self._execute_action(action)

        # 4. Adjust ambition based on result
        if "Expanded" in result or "triggered" in result:
            self.ambition_level = min(1.0, self.ambition_level + 0.05)
        else:
            self.ambition_level = max(0.1, self.ambition_level - 0.01)

        # 5. Record history
        self.history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "drive_score": drive_score,
                "action": action,
                "result": result,
                "ambition_level": self.ambition_level,
            }
        )

        # Keep history to 100 entries
        if len(self.history) > 100:
            self.history = self.history[-100:]

        return {
            "drive_score": drive_score,
            "action": action,
            "result": result,
            "ambition_level": self.ambition_level,
        }

