"""Learner Agent — analyzes experiment results and updates the system.

Inputs: experiment results + current formula configs
Outputs: updated parameters + new hypotheses + system improvements

Closes the NDC 2.0 loop: Question → Experiment → Learn → Question again.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from abvorn.core.reflection import Reflection, ReflectionStore, generate_reflection_id

logger = logging.getLogger(__name__)


def learner_agent(experiment_results: list, formula_configs: dict = None,
                  state: dict = None, model_ask=None) -> dict:
    """Analyze experiment results and produce system updates.

    Args:
        experiment_results: list of completed experiment dicts with outcome data
        formula_configs: current formula parameters (optional)
        state: current system state for persistence
        model_ask: optional callable for AI-powered analysis

    Returns:
        dict with updates, new_hypotheses, system_changes
    """
    learnings = []
    updates = []
    new_hypotheses = []
    system_changes = []

    for exp in experiment_results:
        result = _analyze_experiment(exp)
        if result:
            learnings.append(result)
            if result.get("update"):
                updates.append(result["update"])
            if result.get("new_hypothesis"):
                new_hypotheses.append(result["new_hypothesis"])
            if result.get("system_change"):
                system_changes.append(result["system_change"])

    if model_ask and experiment_results:
        ai_learnings = _generate_with_model(experiment_results, formula_configs, model_ask)
        if ai_learnings:
            if ai_learnings.get("updates"):
                updates.extend(ai_learnings["updates"])
            if ai_learnings.get("new_hypotheses"):
                new_hypotheses.extend(ai_learnings["new_hypotheses"])
            if ai_learnings.get("system_changes"):
                system_changes.extend(ai_learnings["system_changes"])

    if state:
        _persist_learnings(learnings, updates, system_changes, state)

    return {
        "learnings": learnings,
        "updates": updates,
        "new_hypotheses": new_hypotheses,
        "system_changes": system_changes,
        "timestamp": datetime.now().isoformat(),
    }


def _analyze_experiment(experiment: dict) -> dict:
    """Analyze a single experiment result."""
    outcome = experiment.get("outcome", {})
    name = experiment.get("name", "Unknown")
    hypothesis = experiment.get("hypothesis", "")

    if not outcome:
        return None

    result = {
        "experiment_name": name,
        "hypothesis": hypothesis,
        "confirmed": None,
        "effect_size": None,
        "update": None,
        "new_hypothesis": None,
        "system_change": None,
    }

    metrics = outcome.get("metrics", {})
    primary_metric = outcome.get("success_criteria_met", None)

    # RPS Visibility Impact analysis
    if "RPS" in name or "rps" in name.lower():
        return_rate = metrics.get("return_rate_90d", {}).get("change_pct", 0)
        conversion = metrics.get("conversion_rate", {}).get("change_pct", 0)

        if return_rate <= -10:
            result["confirmed"] = True
            result["effect_size"] = abs(return_rate)
            result["update"] = {
                "target": "verdict_engine_layout",
                "change": "Show RPS widget on all article pages by default",
                "rationale": f"RPS visibility reduced return rate by {abs(return_rate)}%",
            }
            result["new_hypothesis"] = {
                "question": "What if showing alternatives alongside RPS further reduces regret?",
                "hypothesis": "Users who see both RPS + ranked alternatives make better decisions than RPS alone.",
                "source": f"learner:{name}",
            }
            result["system_change"] = {
                "component": "rps_widget",
                "change": "ENABLED_BY_DEFAULT = True",
                "rollout": "100%",
            }
        elif return_rate < 0:
            result["confirmed"] = "partial"
            result["effect_size"] = abs(return_rate)
            result["update"] = {
                "target": "rps_thresholds",
                "change": "Adjust RPS severity thresholds — current calibration may be too conservative",
                "rationale": f"RPS showed {abs(return_rate)}% improvement but below 10% target",
            }
            result["new_hypothesis"] = {
                "question": "What if RPS needs to be shown earlier in the buyer journey (before they even land on the product page)?",
                "hypothesis": "Pre-purchase RPS exposure on comparison pages has more impact than post-landing exposure.",
                "source": f"learner:{name}",
            }
        else:
            result["confirmed"] = False
            result["effect_size"] = 0
            result["new_hypothesis"] = {
                "question": "What if the RPS widget's position on the page affects its impact? Bottom-of-page might be too late.",
                "hypothesis": "RPS above-the-fold vs below-the-fold changes behavior.",
                "source": f"learner:{name}",
            }

    # Content Framing Impact analysis
    elif "Content" in name or "framing" in name.lower():
        ctr = metrics.get("affiliate_click_rate", {}).get("change_pct", 0)
        if ctr >= 5:
            result["confirmed"] = True
            result["effect_size"] = ctr
            result["update"] = {
                "target": "content_templates",
                "change": "Update content templates to use winning framing",
                "rationale": f"Alternative framing improved affiliate CTR by {ctr}%",
            }
            result["system_change"] = {
                "component": "content_engine",
                "change": "NEW_DEFAULT_FRAMING = winning_variant",
                "rollout": "50% → monitor → 100%",
            }
        else:
            result["confirmed"] = False
            result["effect_size"] = ctr if ctr else 0

    return result


def _persist_learnings(learnings, updates, system_changes, state):
    """Store learnings in system state."""
    state.setdefault("ndc_learnings", [])
    for l in learnings:
        l["timestamp"] = datetime.now().isoformat()
        state["ndc_learnings"].append(l)

    state.setdefault("ndc_updates", [])
    for u in updates:
        u["applied_at"] = datetime.now().isoformat()
        state["ndc_updates"].append(u)

    state.setdefault("ndc_system_changes", [])
    for c in system_changes:
        c["applied_at"] = datetime.now().isoformat()
        state["ndc_system_changes"].append(c)

    state["ndc_last_learning_cycle"] = datetime.now().isoformat()


def _generate_with_model(experiment_results, formula_configs, model_ask) -> dict:
    """Use model for deeper analysis of experiment results."""
    prompt = f"""You are the Learner Agent. Analyze these experiment results and propose system updates.

Results: {json.dumps(experiment_results, indent=2, default=str)[:2000]}
Current formula parameters: {json.dumps(formula_configs, default=str)[:1000] if formula_configs else 'None'}

Return JSON:
{{"updates": [{{"target":"...","change":"...","rationale":"..."}}],
  "new_hypotheses": [{{"question":"...","hypothesis":"...","source":"learner:ai"}}],
  "system_changes": [{{"component":"...","change":"...","rollout":"..."}}]}}"""

    try:
        result = model_ask(prompt, json_mode=True)
        if result:
            return json.loads(result) if isinstance(result, str) else result
    except Exception:
        pass
    return {}


class HindsightLearner:
    """Hindsight Learner — turns content + performance data into reflections.

    Analyzes why content performed the way it did and records the learnings
    via ReflectionStore (unified SQLite DB + JSONL + optional Obsidian).
    Accepts an optional `model_ask` callable (mirroring `learner_agent`); when
    absent or failing, falls back to a deterministic heuristic reflection so
    the core cycle never crashes.
    """

    def __init__(self, model_ask=None, store: Optional[ReflectionStore] = None):
        self.reflection_store = store if store is not None else ReflectionStore()
        self.model_ask = model_ask or self._default_model_ask
        self.reflection_count = 0

    @staticmethod
    def _default_model_ask(prompt: str, json_mode: bool = False) -> Optional[str]:
        """Route through the real ModelRouter; returns None on any failure."""
        try:
            from abvorn.core.secrets import load_secrets
            from abvorn.core.models import ModelRouter

            router = ModelRouter(load_secrets(), timeout=25)
            return router.ask(
                prompt,
                system="You are the Hindsight Learner for Abvorn. Analyze content performance and return JSON.",
                json_mode=json_mode,
            )
        except Exception as e:
            logger.warning("HindsightLearner model ask failed: %s", e)
            return None

    def generate_reflection(
        self, content_data: Dict, performance_data: Dict
    ) -> Optional[Reflection]:
        """Generate a reflection from content and performance data."""
        try:
            prompt = self._build_reflection_prompt(content_data, performance_data)
            response = self.model_ask(prompt, json_mode=True)
            reflection_data = self._parse_reflection_response(response)

            reflection = Reflection(
                id=generate_reflection_id(),
                generation=content_data.get("generation", 1),
                content_id=content_data.get("id", "unknown"),
                platform=content_data.get("platform", "unknown"),
                original_content=content_data,
                performance_data=performance_data,
                what_worked=reflection_data.get("what_worked", []),
                what_failed=reflection_data.get("what_failed", []),
                why_worked=reflection_data.get("why_worked", []),
                why_failed=reflection_data.get("why_failed", []),
                key_learnings=reflection_data.get("key_learnings", []),
                status="complete",
                generated_by="hindsight_learner",
            )
            self.reflection_store.save(reflection)
            self.reflection_count += 1
            return reflection
        except Exception as e:
            logger.error("Reflection generation failed: %s", e)
            return None

    @staticmethod
    def _build_reflection_prompt(
        content_data: Dict, performance_data: Dict
    ) -> str:
        return (
            "Analyze why this content performed the way it did.\n"
            f"Content: {json.dumps(content_data, default=str)}\n"
            f"Performance: {json.dumps(performance_data, default=str)}\n"
            'Return JSON with keys: what_worked, what_failed, why_worked, '
            'why_failed, key_learnings (all lists of strings).'
        )

    @staticmethod
    def _parse_reflection_response(response) -> Dict:
        """Parse the model response; fall back to a heuristic reflection."""
        expected = {"what_worked", "what_failed", "why_worked", "why_failed", "key_learnings"}
        if isinstance(response, dict) and expected.issubset(response):
            return response
        if isinstance(response, str):
            try:
                parsed = json.loads(response)
                if isinstance(parsed, dict) and expected.issubset(parsed):
                    return parsed
            except (ValueError, TypeError):
                pass
        return {
            "what_worked": ["Content generated successfully"],
            "what_failed": ["No performance data available"],
            "why_worked": ["Content followed the brief"],
            "why_failed": ["Unknown"],
            "key_learnings": ["Improve performance tracking"],
        }
