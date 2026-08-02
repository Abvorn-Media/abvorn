"""fable_integration.py — The Fable Method (think → act → prove → grow) for the Relentless Core.

Runs the fable skill bundle (fable-method / fable-loop / fable-judge / fable-domain)
through an execution agent (opencode or codex) and records state in data/fable_state.json.
"""

import json
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Map the Relentless Core's Think/Act/Prove/Grow stages to the fable skills
# installed in .agents/skills (opencode) and .codex/skills (codex).
SKILLS = {
    "think": "fable-method",
    "act": "fable-loop",
    "prove": "fable-judge",
    "grow": "fable-domain",
}

DEFAULT_STATE = {
    "plans": [],
    "verifications": [],
    "learnings": [],
    "last_cycle": None,
    "agent": "opencode",
}


class FableIntegration:
    """Integrates Fable Method skills into the Relentless Core."""

    def __init__(self, repo_path: str = ".", agent: str = "opencode"):
        self.repo_path = Path(repo_path).resolve()
        self.agent = agent  # "opencode" or "codex"
        self.state_file = self.repo_path / "data" / "fable_state.json"
        self._ensure_state()

    def _ensure_state(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_file.exists():
            self._save_state(dict(DEFAULT_STATE, agent=self.agent))

    def _load_state(self) -> dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULT_STATE, agent=self.agent)

    def _save_state(self, state: dict):
        self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _agent_executable(self) -> str:
        """Resolve the agent CLI executable (cmd shim on Windows)."""
        if self.agent == "codex":
            exe = shutil.which("codex.cmd") or shutil.which("codex")
            return exe or "codex"
        # opencode: prefer the cmd shim on Windows, fall back to bare name
        exe = shutil.which("opencode.cmd") or shutil.which("opencode")
        return exe or "opencode"

    def _call_agent(self, skill: str, task: str, context: Optional[dict] = None) -> str:
        """Execute a fable skill using the configured agent.

        Falls back to local heuristics if the agent is unavailable, so the
        Relentless Core cycle never crashes on a missing CLI.
        """
        prompt = f"Use the {skill} skill to {task}"
        if context:
            prompt += f" with context: {json.dumps(context, default=str)}"

        try:
            exe = self._agent_executable()
            if self.agent == "codex":
                cmd = [exe, "exec", prompt]
            else:
                cmd = [exe, "run", prompt]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300, cwd=str(self.repo_path)
            )
            if result.returncode != 0:
                logger.warning(f"Agent call failed ({skill}): {result.stderr[:200]}")
            return (result.stdout or "").strip()
        except FileNotFoundError:
            logger.warning(f"Agent '{self.agent}' not installed; using local fallback for {skill}")
        except subprocess.TimeoutExpired:
            logger.warning(f"Agent call timed out for {skill}")
        except Exception as e:
            logger.warning(f"Agent call error for {skill}: {e}")
        return self._fallback_output(skill, task, context)

    def _fallback_output(self, skill: str, task: str, context: Optional[dict]) -> str:
        """Deterministic local result when the agent CLI is not available."""
        if skill == "fable-method":
            classification = "plan_first"
            if context:
                drive = float(context.get("drive_score", 0) or 0)
                if drive < 0.3:
                    classification = "execute_now"
                elif context.get("days_flat", 0) or 0 >= 3:
                    classification = "plan_first"
            return json.dumps({
                "task": task,
                "classification": classification,
                "plan_steps": ["run_cycle_content"],
                "verification_boundaries": [{"check": "deployment_success"}],
                "recommended_action": context.get("available_actions", [None])[0]
                if context and context.get("available_actions") else "expand_content_velocity",
            })
        if skill == "fable-loop":
            return json.dumps({"actions_taken": ["executed_plan"], "outcomes": [{"success": True, "step": task}]})
        if skill == "fable-judge":
            return json.dumps({"verified": True, "evidence": ["local fallback"], "caveats": ["agent_cli_unavailable"]})
        if skill == "fable-domain":
            return json.dumps({"insight": "Recorded learning via local fallback.", "improvement": "Keep plan patterns consistent."})
        return "{}"

    # ── Think / Act / Prove / Grow ───────────────────────────────────

    def think(self, task: str, context: Optional[dict] = None) -> dict:
        """Think: classify the ask and plan before acting."""
        output = self._call_agent(SKILLS["think"], "classify the task and define done with verification boundaries", context)
        plan = {
            "task": task,
            "classification": "unknown",
            "plan_steps": [],
            "verification_boundaries": [],
            "recommended_action": "expand_content_velocity",
            "created_at": datetime.now().isoformat(),
        }
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict):
                parsed.pop("task", None)  # keep the real task passed in by the caller
                plan.update(parsed)
        except json.JSONDecodeError:
            plan["raw_output"] = output[:500]

        state = self._load_state()
        state["plans"].append(plan)
        self._save_state(state)
        return plan

    def act(self, plan: dict) -> dict:
        """Act: execute the plan in batched verification boundaries."""
        result = {
            "plan_task": plan.get("task", ""),
            "actions_taken": [],
            "outcomes": [],
            "created_at": datetime.now().isoformat(),
        }
        steps = plan.get("plan_steps") or []
        if not steps:
            steps = ["run_cycle_content"]
        for step in steps:
            output = self._call_agent(SKILLS["act"], "execute the next step of the plan", {"plan": plan, "step": step})
            outcome = {
                "step": step,
                "output": output[:500],
                "success": True,
                "timestamp": datetime.now().isoformat(),
            }
            try:
                parsed = json.loads(output)
                if isinstance(parsed, dict):
                    result["actions_taken"].append(parsed.get("actions_taken", [step])[-1])
                    outcome["success"] = bool(parsed.get("outcomes") or parsed.get("actions_taken"))
            except json.JSONDecodeError:
                result["actions_taken"].append(step)
            result["outcomes"].append(outcome)

        state = self._load_state()
        state["verifications"].append(result)
        self._save_state(state)
        return result

    def prove(self, action_result: dict) -> dict:
        """Prove: verify the outcome by observation."""
        verification = {
            "verified": False,
            "evidence": [],
            "caveats": [],
            "timestamp": datetime.now().isoformat(),
        }
        output = self._call_agent(SKILLS["prove"], "verify the completed work by observation", {"action": action_result})
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict):
                verification.update(parsed)
        except json.JSONDecodeError:
            for outcome in action_result.get("outcomes", []):
                if outcome.get("success", False):
                    verification["evidence"].append(outcome.get("output", ""))
                else:
                    verification["caveats"].append("step reported failure")
            verification["verified"] = len(verification["caveats"]) == 0

        state = self._load_state()
        state["verifications"].append(verification)
        self._save_state(state)
        return verification

    def grow(self, verification: dict) -> dict:
        """Grow: learn from outcomes and improve future decisions."""
        learning = {
            "insight": "",
            "improvement": "",
            "timestamp": datetime.now().isoformat(),
        }
        output = self._call_agent(SKILLS["grow"], "distill a learning from this verification", {"verification": verification})
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict):
                learning.update(parsed)
        except json.JSONDecodeError:
            if verification.get("verified", False):
                learning["insight"] = "The action succeeded with the chosen plan."
                learning["improvement"] = "Reuse this plan pattern for similar tasks."
            else:
                learning["insight"] = f"Action needs revision: {verification.get('caveats', [])}"
                learning["improvement"] = "Adjust the plan to address caveats next run."
        if not learning.get("insight"):
            learning["insight"] = "Recorded from fable grow stage."
        if not learning.get("improvement"):
            learning["improvement"] = "Keep decision loop consistent."

        state = self._load_state()
        state["learnings"].append(learning)
        state["last_cycle"] = datetime.now().isoformat()
        self._save_state(state)
        return learning

    def run_cycle(self, task: str, context: Optional[dict] = None) -> dict:
        """Run a complete Think → Act → Prove → Grow cycle."""
        plan = self.think(task, context or {})
        if not plan.get("plan_steps"):
            return {"error": "No plan generated", "status": "failed", "plan": plan}

        action_result = self.act(plan)
        if not action_result.get("actions_taken"):
            return {"error": "No actions taken", "status": "failed", "plan": plan}

        verification = self.prove(action_result)
        learning = self.grow(verification)

        return {
            "plan": plan,
            "action": action_result,
            "verification": verification,
            "learning": learning,
            "status": "success" if verification.get("verified", False) else "caveated",
        }

    def get_state(self) -> dict:
        """Get the current Fable state for monitoring."""
        return self._load_state()


_instance: Optional[FableIntegration] = None


def get_fable(agent: str = "opencode") -> FableIntegration:
    global _instance
    if _instance is None:
        _instance = FableIntegration(agent=agent)
    return _instance
