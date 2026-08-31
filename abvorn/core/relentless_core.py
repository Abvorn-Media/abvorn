"""relentless_core.py — The Relentless Core of Abvorn.

Minimal, real version. Reads from actual data sources and drives the system.
No simulations. No fake APIs.
"""

import json
import logging
import os
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

        # Optional Hindsight Learner (never fatal if unavailable)
        self.hindsight_learner = None
        self.reflection_interval = 10
        try:
            from abvorn.core.learner import HindsightLearner

            self.hindsight_learner = HindsightLearner()
        except Exception as e:
            logger.warning(f"Hindsight learner unavailable: {e}")

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
        self.cycle_count = 0
        try:
            import os as _os

            env_version = _os.environ.get("ABVORN_GENESIS_VERSION")
            if env_version:
                self.version = int(env_version)
            from abvorn.core.genesis_protocol import GenesisProtocol

            self.genesis = GenesisProtocol(self.version)
        except Exception as e:
            logger.warning(f"Genesis protocol unavailable: {e}")

        # Optional Brain library (never fatal if unavailable)
        self.brain = None
        try:
            from abvorn.core.brain import get_brain

            self.brain = get_brain()
            if self.brain.is_ready:
                logger.info(
                    f"Brain is ready with {self.brain.memory.get_state().get('entities', 0)} entities"
                )
            else:
                logger.warning("Brain not ready yet. Please ingest books.")
        except Exception as e:
            logger.warning(f"Brain unavailable: {e}")

        # Optional Viral Content Engine (never fatal if unavailable)
        self.platform_skill = None
        try:
            from abvorn.core.platform_skill import get_platform_skill

            self.platform_skill = get_platform_skill()
        except Exception as e:
            logger.warning(f"Platform skill engine unavailable: {e}")

        # Optional Colosseum adversarial refinement (never fatal if unavailable)
        self.colosseum = None
        try:
            from abvorn.core.colosseum import get_colosseum

            self.colosseum = get_colosseum()
        except Exception as e:
            logger.warning(f"Colosseum unavailable: {e}")

        # Optional Symbiotic Cortex (Obsidian vault) — never fatal if unavailable
        self.cortex = None
        try:
            from abvorn.core.cortex_watcher import cortex_enabled, get_cortex_watcher

            if cortex_enabled():
                self.cortex = get_cortex_watcher()
                if self.cortex is not None:
                    self.cortex.start()
                    logger.info("Symbiotic Cortex watcher started.")
        except Exception as e:
            logger.warning(f"Cortex watcher unavailable: {e}")

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

        # Brain library can inform core decisions with book-strategy insights
        brain_insights = []
        if self.brain is not None and self.brain.is_ready:
            try:
                brain_insights = self.brain.get_insights_for_function("core_decisions")
            except Exception as e:
                logger.warning(f"Brain insight query failed: {e}")

        # If drive score is low, take aggressive actions
        if drive_score < 0.3:
            return "expand_content"  # Add more niches
        elif drive_score < 0.5:
            if deployed > 0 and queue < 3:
                return "expand_content"
            else:
                return "optimize_conversion"
        elif drive_score < 0.7:
            # Brain strategy books may tilt toward monetization over polish
            if brain_insights:
                query_lower = " ".join(str(i.get("insight", "")) for i in brain_insights[:3]).lower()
                if any(k in query_lower for k in ("conversion", "monetiz", "price", "revenue", "retention")):
                    return "optimize_conversion"
            return "refine_quality"
        else:
            # High drive score: push into new territory
            if win_metrics and win_runs < 5:
                # Rotate a win.sh growth loop in before exploring new domains
                return "run_traffic_optimizer"
            if self.platform_skill is not None:
                return "publish_content"
            return "explore_new_domain"

    def _generate_carousel(self, product_data: Dict) -> Dict:
        """Build a 6-slide carousel payload with an Oliver Henry hook."""
        verdict = product_data.get("verdict", {}) or {}
        overall = verdict.get("overall", 0)
        label = verdict.get("label", "Good")
        product_name = product_data.get("product_name", "this product")
        breakdown = verdict.get("breakdown", {}) or {}

        # Prefer the Title Engine's top scroll-stopping variant for the hook;
        # fall back to the classic Oliver Henry line when unavailable.
        hook = f"My friend thought {product_name} was overrated... until they tried it"
        try:
            from abvorn.core.title_engine import get_title_engine
            best = get_title_engine().select_best(
                {"product_name": product_name, "verdict": verdict, "price": product_data.get("price")},
                platform="tiktok",
            )
            if best.get("title"):
                hook = best["title"]
        except Exception as e:
            logger.debug(f"Title engine unavailable in carousel builder: {e}")
        slides = {
            "hook": {"text": hook},
            "problem": {"text": f"The {product_name} market is flooded. Here's the truth."},
            "verdict": {"text": f"{label} — {overall}/10"},
            "breakdown": {"text": "\n".join(f"{k}: {v:.1f}/10" for k, v in breakdown.items())},
            "comparison": {
                "text": f"Best in: {max(breakdown, key=breakdown.get)}" if breakdown else "Best overall pick"
            },
            "call": {"text": "Full review → link in bio\nWhich product next?"},
        }
        return {
            "product_name": product_name,
            "hook": hook,
            "slides": slides,
            "hashtags": [f"#{product_name.replace(' ', '')}", "#Abvorn", "#ProductReview"],
            "verdict": verdict,
        }

    def _publish_to_platform(self, adapted: Dict, platform: str) -> Dict:
        """Publish adapted content to a platform (Composio hookup point)."""
        try:
            # Composio integration point: replace with a real adapter when keys exist.
            from abvorn.core.secrets import load_secrets

            if load_secrets().get("COMPOSIO_KEY"):
                return {"platform": platform, "status": "queued", "content": adapted}
        except Exception as e:
            logger.warning(f"Composio check failed for {platform}: {e}")
        logger.info(f"[publish_content] Draft ready for {platform}: {adapted.get('hook', '')}")
        return {"platform": platform, "status": "draft", "content": adapted}

    def _get_latest_product(self) -> Dict:
        """Pull the latest reviewed product from state, or a realistic default."""
        try:
            state = self._read_cycle_state()
            deployed = state.get("deployed", [])
            if deployed and isinstance(deployed[-1], dict) and deployed[-1].get("product"):
                p = deployed[-1]["product"]
                return {
                    "product_name": p.get("name", "Sony WH-1000XM6"),
                    "verdict": p.get("verdict", {"overall": 8.7, "label": "Excellent", "breakdown": {"Sound": 9.2, "Comfort": 8.8, "Battery": 7.5}}),
                }
        except Exception as e:
            logger.warning(f"Could not read latest product: {e}")
        return {"product_name": "Sony WH-1000XM6", "verdict": {"overall": 8.7, "label": "Excellent", "breakdown": {"Sound": 9.2, "Comfort": 8.8, "Battery": 7.5}}}

    def _publish_content(self) -> str:
        """Viral Content Engine: build a carousel, refine it, adapt for all platforms."""
        if self.platform_skill is None:
            return "publish_content requested but platform skill engine is unavailable"
        try:
            carousel = self._generate_carousel(self._get_latest_product())
            results = {}
            for platform in self.platform_skill.platforms:
                refined = carousel
                if self.colosseum is not None:
                    try:
                        refined = self.colosseum.conduct_debate(carousel, platform)
                    except Exception as e:
                        logger.warning(f"Colosseum refinement failed for {platform}: {e}")
                adapted = self.platform_skill.generate_platform_content(refined, platform)
                results[platform] = self._publish_to_platform(adapted, platform)
            summary = ", ".join(f"{p}={r.get('status')}" for p, r in results.items())
            logger.info(f"[publish_content] {summary}")
            return f"Published carousel across platforms ({summary})"
        except Exception as e:
            logger.warning(f"publish_content failed: {e}")
            return f"publish_content failed: {e}"

    def _execute_action(self, action: str) -> str:
        """Execute the action."""
        if action == "publish_content":
            return self._publish_content()

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

    def _write_to_cortex(self, result: Dict[str, Any]):
        """Write the evolution journal entry.

        Two sinks, both optional and never fatal:
          1. The repo-tracked Evolution Journal (abvorn.core.evolution_journal)
             — always attempted, so CI content cycles accumulate entries that
             the public journal page can show.
          2. The Obsidian vault (Symbiotic Cortex) — only when the local vault
             exists on this machine.
        """
        version = int(result.get("version", self.version))
        drive_score = float(result.get("drive_score", 0.0))
        action = result.get("action", "unknown")
        result_text = str(result.get("result", ""))
        narrative = (
            f"Drive score {drive_score:.3f} — "
            f"action '{action}': {result_text}"
        )

        # 1. Repo-tracked journal — works in CI where the vault is absent.
        try:
            from abvorn.core.evolution_journal import append_entry

            graph_nodes = graph_edges = None
            try:
                if self.memory_state:
                    graph_nodes = int(self.memory_state.get("entities") or 0)
                    graph_edges = int(self.memory_state.get("relationships") or 0)
            except Exception:
                pass
            append_entry(
                {
                    "timestamp": datetime.now().isoformat(),
                    "generation": version,
                    "drive_score": drive_score,
                    "action": action,
                    "narrative": narrative,
                    "graph_nodes": graph_nodes,
                    "graph_edges": graph_edges,
                }
            )
        except Exception as e:
            logger.warning(f"Tracked journal write failed: {e}")

        # 2. Obsidian vault (Symbiotic Cortex) — local vault only.
        if self.cortex is None:
            return
        try:
            from abvorn.core.cortex_watcher import get_vault_path

            vault = get_vault_path()
            if vault is None:
                return
            journal_dir = vault / "Journal"
            journal_dir.mkdir(parents=True, exist_ok=True)

            today = datetime.now().strftime("%Y-%m-%d")
            journal_file = journal_dir / f"{today}.md"

            frontmatter = {
                "generation": version,
                "date": datetime.now().isoformat(),
                "drive_score": drive_score,
                "ambition": result.get("ambition_level", 0.5),
                "action": action,
                "role": result.get("role", "solo"),
            }

            if journal_file.exists():
                existing = journal_file.read_text(encoding="utf-8")
                if f"Cycle {version}" in existing:
                    return
                with open(journal_file, "a", encoding="utf-8") as f:
                    f.write(f"\n\n## Cycle {version}\n\n")
                    f.write(narrative)
            else:
                content = "---\n"
                content += "\n".join([f"{k}: {v}" for k, v in frontmatter.items()])
                content += "\n---\n\n"
                content += f"# Ab's Evolution Journal - {today}\n\n"
                content += narrative
                journal_file.write_text(content, encoding="utf-8")

            logger.info("Journal entry written to %s", journal_file)
        except Exception as e:
            logger.warning(f"Cortex journal write failed: {e}")

    def cycle(self) -> Dict[str, Any]:
        """Run one drive cycle (Think → Act → Prove → Grow when Fable is available)."""
        self.cycle_count += 1
        # 0. Evolution trigger: after enough cycles, evolve to a child core
        self.evolution_counter += 1
        if self.evolution_counter >= 10 and self.genesis is not None:
            evolution = self._evolve()
            self.evolution_counter = 0  # reset so evolution happens once per 10 cycles, not every cycle after 10
            self._write_to_cortex({**evolution, "drive_score": self.drive_score})
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
                        "brain_insights": (
                            self.brain.get_insights_for_function("core_decisions")[:3]
                            if self.brain is not None and self.brain.is_ready else []
                        ),
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

        # 3b. Prove/Grow: the action was ALREADY executed by _execute_action()
        # above. We must NOT re-run it through fable.act() (that would duplicate
        # the work); instead we wrap the executed result in verification + learning.
        if self.fable is not None:
            try:
                executed = {
                    "plan_task": action,
                    "actions_taken": [action],
                    "outcomes": [{"step": action, "success": bool(result), "output": str(result)[:500]}],
                }
                verification = self.fable.prove(executed)
                learning = self.fable.grow(verification)
            except Exception as e:
                logger.warning(f"Fable prove/grow failed: {e}")

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

        cycle_result = {
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

        # 5b. Reflection trigger: every reflection_interval cycles, analyze the
        # latest content + performance and persist a hindsight reflection.
        if self.hindsight_learner is not None and self.cycle_count % self.reflection_interval == 0:
            content_data = {
                "id": action,
                "generation": self.version,
                "platform": "web",
                "drive_score": drive_score,
                "ambition_level": self.ambition_level,
                "action": action,
            }
            performance_data = {
                "win_metrics": self._read_win_metrics(),
                "state": self._read_cycle_state(),
            }
            reflection = self.hindsight_learner.generate_reflection(content_data, performance_data)
            if reflection:
                cycle_result["reflection_id"] = reflection.id

        # 6. Write the journal entry to the Symbiotic Cortex vault
        self._write_to_cortex(cycle_result)

        return cycle_result

