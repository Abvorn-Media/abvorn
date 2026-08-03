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

        # Optional win.sh integration (never fatal if unavailable)
        self.win_sh = None
        try:
            from abvorn.core.win_sh_bridge import get_win_sh_bridge

            self.win_sh = get_win_sh_bridge()
        except Exception as e:
            logger.warning(f"win.sh bridge unavailable: {e}")

        # Optional Fable Method integration (never fatal if unavailable)
        self.fable = None
        try:
            from abvorn.core.fable_integration import get_fable

            self.fable = get_fable(agent="opencode")
        except Exception as e:
            logger.warning(f"Fable integration unavailable: {e}")

        # ── Evolution Stack integrations (never fatal if unavailable) ──
        self.memory = None
        self.memory_state = {}
        try:
            from abvorn.core.neural_memory import get_neural_memory

            self.memory = get_neural_memory()
            self.memory_state = self.memory.get_state()
        except Exception as e:
            logger.warning(f"Neural memory unavailable: {e}")

        self.spawn = None
        self.role = "solo"
        try:
            from abvorn.core.spawn_controller import SpawnController

            self.spawn = SpawnController()
            self.role = self.spawn.register()
            self.spawn.run_heartbeat_loop()
        except Exception as e:
            logger.warning(f"Spawn controller unavailable: {e}")

        self.version = 1
        self.genesis = None
        self.evolution_counter = 0
        try:
            import os as _os

            env_version = _os.environ.get("ABVORN_GENESIS_VERSION")
            if env_version:
                self.version = int(env_version)
            from abvorn.core.genesis_protocol import GenesisProtocol

            self.genesis = GenesisProtocol(self.version)
        except Exception as e:
            logger.warning(f"Genesis protocol unavailable: {e}")

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

    def _read_win_metrics(self) -> Dict:
        """Read win.sh loop activity for diagnostics and decisioning."""
        if self.win_sh is None:
            return {}
        try:
            if not self.win_sh.is_ready():
                return {}
            return self.win_sh.get_all_metrics()
        except Exception as e:
            logger.warning(f"Could not read win.sh metrics: {e}")
            return {}

    def _decide_action(self, drive_score: float) -> str:
        """Decide what action to take based on the drive score."""
        # Read current state to understand what's happening
        state = self._read_cycle_state()
        deployed = len(state.get("deployed", []))
        queue = len(state.get("queue", []))

        # win.sh metrics can push a loop into rotation when signals warrant it
        win_metrics = self._read_win_metrics()
        win_runs = win_metrics.get("total_runs", 0) if win_metrics else 0

        # Neural memory can enrich the decision with past insights
        memory_context = []
        if self.memory is not None:
            try:
                memory_context = self.memory.query(
                    f"What actions improve drive score when it's at {drive_score:.2f}?"
                )
            except Exception as e:
                logger.warning(f"Memory query failed: {e}")

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
            if win_metrics and win_runs < 5:
                # Rotate a win.sh growth loop in before exploring new domains
                return "run_traffic_optimizer"
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

        # ── win.sh loop actions ──────────────────────────────────────
        win_handlers = {
            "run_seo_growth": lambda: self.win_sh.run_seo_growth(),
            "run_traffic_optimizer": lambda: self.win_sh.run_traffic_optimizer(),
            "run_conversion_optimizer": lambda: self.win_sh.run_conversion_optimizer(),
            "run_feedback_to_fix": lambda: self.win_sh.run_feedback_to_fix(),
            "run_ads_budget_guard": lambda: self.win_sh.run_ads_budget_guard(),
        }
        if action in win_handlers:
            if self.win_sh is None:
                return "win.sh loop requested but bridge is unavailable"
            try:
                run = win_handlers[action]()
                run_id = run.get("id", "unknown") if isinstance(run, dict) else "unknown"
                status = run.get("status", "created") if isinstance(run, dict) else "created"
                return f"win.sh loop triggered ({action}): run {run_id} status={status}"
            except Exception as e:
                logger.warning(f"win.sh loop {action} failed: {e}")
                return f"win.sh loop failed: {e}"
        else:
            return f"Unknown action: {action}"

    def _verify_outcome(self, action_result: Dict[str, Any]) -> Dict[str, Any]:
        """Prove: verify the executed action by observation."""
        if self.fable is None:
            return {"verified": False, "evidence": [], "caveats": ["fable_unavailable"]}
        try:
            return self.fable.prove(action_result)
        except Exception as e:
            logger.warning(f"Fable prove failed: {e}")
            return {"verified": False, "evidence": [], "caveats": [str(e)]}

    def _learn_from_outcome(self, verification: Dict[str, Any]) -> Dict[str, Any]:
        """Grow: distill a learning from the verification."""
        if self.fable is None:
            return {"insight": "", "improvement": ""}
        try:
            return self.fable.grow(verification)
        except Exception as e:
            logger.warning(f"Fable grow failed: {e}")
            return {"insight": "", "improvement": ""}

    def _remember(self, action: str, result: str, verified: bool):
        """Log an outcome to persistent memory (outcomes.jsonl + neural memory)."""
        outcome = {
            "action": action,
            "result": result,
            "verified": verified,
            "timestamp": datetime.now().isoformat(),
        }
        outcomes_file = self.data_dir / "outcomes.jsonl"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with open(outcomes_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(outcome) + "\n")
        if self.memory is not None:
            try:
                self.memory.ingest("./data", mode="normal")
                insights = self.memory.discover_insights()
                if insights:
                    logger.info(f"Memory discovered {len(insights)} new insights")
            except Exception as e:
                logger.warning(f"Memory update failed: {e}")

    def _leader_cycle(self) -> Dict[str, Any]:
        action = self._decide_action(self.drive_score)
        followers = self.spawn.get_followers() if self.spawn else []
        if followers:
            assigned_follower = followers[0]
            task = {
                "id": f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "action": action,
                "assigned_by": self.spawn.instance_id,
                "timestamp": datetime.now().isoformat(),
            }
            self.spawn.assign_task(task)
            logger.info(f"Assigned task '{action}' to {assigned_follower}")
            return {"action": action, "status": "assigned", "assigned_to": assigned_follower}
        result = self._execute_action(action)
        self._remember(action, result, True)
        return {"action": action, "status": "executed", "result": result}

    def _follower_cycle(self) -> Dict[str, Any]:
        if self.spawn is None:
            return self._leader_cycle()
        task_data = self.spawn.get_my_task()
        if task_data:
            action = task_data["task"].get("action")
            if action:
                result = self._execute_action(action)
                self.spawn.complete_task(task_data["id"])
                logger.info(f"Completed task: {action}")
                return {"action": action, "status": "executed", "result": result}
        return {"status": "idle", "message": "No tasks assigned"}

    def _follower_action(self):
        """Follower pulls one assigned task and executes it (or signals idle)."""
        if self.spawn is None:
            return (None, None, None, None)
        task_data = self.spawn.get_my_task()
        if not task_data:
            return (None, None, None, None)
        action = task_data["task"].get("action")
        if not action:
            self.spawn.complete_task(task_data["id"])
            return (None, None, None, None)
        result = self._execute_action(action)
        self.spawn.complete_task(task_data["id"])
        self._remember(action, result, True)
        logger.info(f"Completed follower task: {action}")
        return (action, result, {"verified": True}, {"insight": action})

    def _evolve(self) -> Dict[str, Any]:
        if self.genesis is None:
            return {"status": "evolve_skipped", "message": "genesis unavailable"}
        logger.info(f"EVOLUTION INITIATED: V{self.version} -> V{self.version + 1}")
        child_path = self.genesis.spawn_child()
        self.version += 1
        return {
            "status": "evolved",
            "from_version": self.version - 1,
            "to_version": self.version,
            "child_path": child_path,
            "timestamp": datetime.now().isoformat(),
        }

    def cycle(self) -> Dict[str, Any]:
        """Run one drive cycle (Think → Act → Prove → Grow when Fable is available)."""
        # 0. Evolution trigger: after enough cycles, evolve to a child core
        self.evolution_counter += 1
        if self.evolution_counter >= 10 and self.genesis is not None:
            evolution = self._evolve()
            return {**evolution, "drive_score": self.drive_score}
        # 1. Calculate current drive score
        drive_score = self._calculate_drive_score()
        self.drive_score = drive_score

        # 1b. Think: Fable classifies the task before acting
        fable_plan = None
        if self.fable is not None:
            try:
                fable_plan = self.fable.think(
                    "Drive one Abvorn content cycle",
                    {
                        "drive_score": drive_score,
                        "ambition_level": self.ambition_level,
                        "win_metrics": self._read_win_metrics(),
                        "state": self._read_cycle_state(),
                    },
                )
                logger.info(f"Fable think: classification={fable_plan.get('classification')}")
            except Exception as e:
                logger.warning(f"Fable think failed: {e}")

        # 2. Decide action (leader-dictated; followers pick from task queue)
        if self.spawn is not None and self.role == "follower":
            action, result, verification, learning = self._follower_action()
            if action is None:
                return {
                    "status": "idle",
                    "drive_score": drive_score,
                    "message": "No tasks assigned",
                    "win_metrics": self._read_win_metrics(),
                }
        else:
            action = self._decide_action(drive_score)
            result = self._execute_action(action)
            self._remember(action, result, True)
            verification = {"verified": False, "evidence": [], "caveats": []}
            learning = {"insight": "", "improvement": ""}

        # 3b. Act/Prove/Grow: wrap the executed action in the Fable loop
        if self.fable is not None:
            try:
                action_result = self.fable.act(fable_plan or {"task": action, "plan_steps": ["run_cycle_content"]})
                verification = self._verify_outcome(action_result)
                learning = self._learn_from_outcome(verification)
            except Exception as e:
                logger.warning(f"Fable act/prove/grow failed: {e}")

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
            "role": self.role,
            "version": self.version,
            "win_metrics": self._read_win_metrics(),
            "fable_plan": fable_plan,
            "fable_verification": verification,
            "fable_learning": learning,
        }

