"""win_sh_bridge.py — Bridge between the Relentless Core and win.sh loops.

win.sh (`@win.sh/win`) is a local harness that runs autonomous business loops
(seo-growth, traffic-growth-optimizer, conversion-optimizer, feedback-to-fix,
ads-budget-guard). This module lets the Relentless Core trigger loops and read
their journals, run briefs, executions, artifacts, and outcomes.

State lives in `.win/state/*.jsonl` (append-only). Run briefs are created by
`win run <loop>` and executed by an agent (`win exec`). This bridge only
triggers and reads — the agent execution is out of scope for the Python layer.
"""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Loops this bridge can drive, keyed by the Relentless Core action name.
LOOP_ACTIONS: Dict[str, str] = {
    "run_seo_growth": "seo-growth",
    "run_traffic_optimizer": "traffic-growth-optimizer",
    "run_conversion_optimizer": "conversion-optimizer",
    "run_feedback_to_fix": "feedback-to-fix",
    "run_ads_budget_guard": "ads-budget-guard",
}


class WinShBridge:
    """Bridge between Relentless Core and win.sh loops."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        self.win_state = self.repo_path / ".win" / "state"
        self.agent = os.environ.get("WIN_AGENT", "codex")
        self._ensure_win()

    # ── CLI resolution ──────────────────────────────────────────────

    def _find_win(self) -> str:
        """Locate the `win` executable (win.cmd on Windows)."""
        candidates = [
            shutil.which("win"),
            shutil.which("win.cmd"),
            str(Path(os.environ.get("APPDATA", "")) / "npm" / "win.cmd"),
            str(Path.home() / "AppData" / "Roaming" / "npm" / "win.cmd"),
        ]
        for c in candidates:
            if c and Path(c).exists():
                return c
        raise RuntimeError("win.sh not installed. Run: npm install -g @win.sh/win")

    def _ensure_win(self) -> None:
        """Fail fast if the win CLI is unavailable."""
        try:
            self._find_win()
        except RuntimeError as e:
            logger.error(str(e))
            raise

    # ── Core loop runner ────────────────────────────────────────────

    def _run_loop(self, loop_name: str, signal: str = "") -> Dict[str, Any]:
        """Trigger a win.sh loop and return the run brief it creates."""
        win = self._find_win()
        cmd = [win, "run", loop_name, "--repo", str(self.repo_path), "--trigger", "manual"]
        if signal:
            cmd += ["--signal", signal]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        except subprocess.TimeoutExpired:
            return {"error": "win run timed out", "returncode": -1}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"output": result.stdout, "error": result.stderr, "returncode": result.returncode}

    # ── State readers (JSONL) ───────────────────────────────────────

    def _read_jsonl(self, name: str) -> List[Dict]:
        """Read a .win/state JSONL file into a list of dicts."""
        path = self.win_state / name
        if not path.exists():
            return []
        entries = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def get_runs(self, loop_name: Optional[str] = None) -> List[Dict]:
        """All run briefs, optionally filtered by loop."""
        runs = self._read_jsonl("runs.jsonl")
        if loop_name:
            runs = [r for r in runs if r.get("loopId") == loop_name]
        return runs

    def get_executions(self, loop_name: Optional[str] = None) -> List[Dict]:
        """Execution records, optionally filtered by loop."""
        executions = self._read_jsonl("executions.jsonl")
        if loop_name:
            executions = [e for e in executions if e.get("loopId") == loop_name]
        return executions

    def get_outcomes(self, loop_name: Optional[str] = None) -> List[Dict]:
        """Outcome records, optionally filtered by loop."""
        outcomes = self._read_jsonl("outcomes.jsonl")
        if loop_name:
            outcomes = [o for o in outcomes if o.get("loopId") == loop_name]
        return outcomes

    def get_artifacts(self, loop_name: Optional[str] = None) -> List[Dict]:
        """Attached artifacts, optionally filtered by loop."""
        artifacts = self._read_jsonl("artifacts.jsonl")
        if loop_name:
            artifacts = [a for a in artifacts if a.get("loopId") == loop_name]
        return artifacts

    def get_latest_outcome(self, loop_name: str) -> Optional[Dict]:
        """Most recent outcome record for a loop."""
        outcomes = self.get_outcomes(loop_name)
        return outcomes[-1] if outcomes else None

    def get_latest_run(self, loop_name: str) -> Optional[Dict]:
        """Most recent run brief for a loop."""
        runs = self.get_runs(loop_name)
        return runs[-1] if runs else None

    # ── Individual loop wrappers ────────────────────────────────────

    def run_seo_growth(self, signal: str = "") -> Dict:
        return self._run_loop("seo-growth", signal or "Abvorn SEO growth check: review page metadata, internal linking, and schema on review pages.")

    def run_traffic_optimizer(self, signal: str = "") -> Dict:
        return self._run_loop("traffic-growth-optimizer", signal or "Abvorn traffic experiment: identify the highest-leverage acquisition or keyword move.")

    def run_conversion_optimizer(self, signal: str = "") -> Dict:
        return self._run_loop("conversion-optimizer", signal or "Abvorn conversion check: review CTA and affiliate link prominence on review pages.")

    def run_feedback_to_fix(self, issue_text: str = "") -> Dict:
        return self._run_loop("feedback-to-fix", issue_text or "Abvorn feedback triage: route outstanding support or issue signals.")

    def run_ads_budget_guard(self, signal: str = "") -> Dict:
        return self._run_loop("ads-budget-guard", signal or "Abvorn ad budget check: review spend and pause/scale decisions if any ads run.")

    # ── Aggregated metrics for the Core ─────────────────────────────

    def get_all_metrics(self) -> Dict[str, Any]:
        """Aggregate win.sh activity into a compact metrics dict for the Core."""
        metrics: Dict[str, Any] = {}
        for action, loop_name in LOOP_ACTIONS.items():
            runs = self.get_runs(loop_name)
            outcomes = self.get_outcomes(loop_name)
            completed = [o for o in outcomes if str(o.get("status", "")).lower() == "complete"]
            metrics[loop_name] = {
                "runs": len(runs),
                "outcomes": len(outcomes),
                "completed": len(completed),
                "latest_status": outcomes[-1].get("status") if outcomes else None,
            }
        per_loop = [m for k, m in metrics.items() if k in LOOP_ACTIONS.values()]
        metrics["total_runs"] = sum(m["runs"] for m in per_loop)
        metrics["total_outcomes"] = sum(m["outcomes"] for m in per_loop)
        metrics["total_completed"] = sum(m["completed"] for m in per_loop)
        return metrics

    def is_ready(self) -> bool:
        """True if at least one loop is installed and enabled."""
        for loop_name in LOOP_ACTIONS.values():
            state_path = self.repo_path / ".win" / "loops" / loop_name / "state.json"
            if state_path.exists():
                try:
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    if state.get("enabled", False):
                        return True
                except Exception:
                    continue
        return False


_instance: Optional[WinShBridge] = None


def get_win_sh_bridge() -> WinShBridge:
    """Return a process-wide singleton bridge."""
    global _instance
    if _instance is None:
        _instance = WinShBridge()
    return _instance
