"""Experimenter Agent — designs A/B tests and data collection strategies.

Inputs: hypotheses from Questioner Agent
Outputs: structured experiment designs with metrics, duration, success criteria
"""

import json
from datetime import datetime, timedelta


def experimenter_agent(questions: list, model_ask=None) -> list:
    """Convert hypotheses into structured experiment designs.

    Args:
        questions: list of question dicts from Questioner Agent
        model_ask: optional callable for AI-powered experiment design

    Returns:
        list of experiment dicts
    """
    experiments = []
    for q in questions:
        exp = _design_experiment(q)
        if exp:
            experiments.append(exp)

    if model_ask and questions:
        ai_exps = _generate_with_model(questions, model_ask)
        if ai_exps:
            experiments.extend(ai_exps)

    return experiments


def _design_experiment(question: dict) -> dict:
    """Convert a single question into an experiment design."""
    exp_idea = question.get("experiment_idea", "")
    severity = question.get("severity", "medium")

    base = {
        "source_question": question.get("question", ""),
        "source_hypothesis": question.get("hypothesis", ""),
        "source_formula": question.get("source_formula", ""),
        "status": "designed",
        "created_at": datetime.now().isoformat(),
    }

    if "RPS" in exp_idea or "rps" in exp_idea or "regret" in exp_idea.lower():
        return {
            **base,
            "type": "a/b_test",
            "name": "RPS Visibility Impact",
            "hypothesis": "Showing RPS before purchase improves decision quality.",
            "test_groups": [
                {"name": "Control", "description": "Standard product page — no RPS widget visible"},
                {"name": "Treatment", "description": "RPS widget displayed prominently above buy button"},
            ],
            "metrics": ["conversion_rate", "return_rate_90d", "avg_order_value", "repeat_purchase_rate"],
            "sample_size_min": 1000,
            "duration_days": 90,
            "success_criteria": {"primary": "return_rate decreases by >=10%", "secondary": "repeat_purchase_rate increases by >=5%"},
            "risk": "Conversion may drop if RPS discourages borderline purchases — acceptable if return rate improves.",
        }

    if "A/B test" in exp_idea or "ab test" in exp_idea.lower():
        return {
            **base,
            "type": "a/b_test",
            "name": "Content Framing Impact",
            "hypothesis": question.get("hypothesis", "Content framing affects user perception."),
            "test_groups": [
                {"name": "Control", "description": "Standard content layout"},
                {"name": "Treatment", "description": "Alternative framing as described in hypothesis"},
            ],
            "metrics": ["click_through_rate", "time_on_page", "affiliate_click_rate"],
            "sample_size_min": 500,
            "duration_days": 30,
            "success_criteria": {"primary": "affiliate_click_rate increases by >=5%"},
            "risk": "Low — changes are content-only, no technical risk.",
        }

    if "survey" in exp_idea.lower():
        return {
            **base,
            "type": "survey",
            "name": "User Sentiment Survey",
            "hypothesis": question.get("hypothesis", ""),
            "method": "Targeted email or on-page survey to users who purchased [timeframe] ago",
            "metrics": ["response_rate", "satisfaction_score", "regret_triggers"],
            "questions": [
                "On a scale of 1-10, how satisfied are you with your purchase?",
                "What, if anything, do you regret about your purchase?",
                "When did you first feel this way? (immediately / within a week / within a month / later)",
                "What would have helped you make a better decision?",
            ],
            "sample_size_min": 200,
            "duration_days": 14,
            "success_criteria": {"primary": ">=30% response rate with actionable insights"},
            "risk": "Low — survey fatigue is main concern.",
        }

    return {
        **base,
        "type": "data_collection",
        "name": "Observational Study",
        "hypothesis": question.get("hypothesis", ""),
        "method": "Collect additional metadata on product pages and correlate with existing metrics",
        "metrics": ["data_points_collected", "feature_coverage", "signal_noise_ratio"],
        "data_points_needed": ["user_preference_profile", "product_scores", "interaction_timestamps"],
        "duration_days": 30,
        "success_criteria": {"primary": "Collect >=1000 data points with sufficient variance"},
        "risk": "None — passive data collection.",
    }


def _generate_with_model(questions, model_ask) -> list:
    """Use model to design more sophisticated experiments."""
    prompt = f"""You are the Experimenter Agent. Design a rigorous experiment for this hypothesis:

Questions: {json.dumps([q.get("question") for q in questions], indent=2)}
Hypotheses: {json.dumps([q.get("hypothesis") for q in questions], indent=2)}

Return a JSON array of experiment objects:
[{{"name": "...", "type": "a/b_test|survey|data_collection", "hypothesis": "...",
   "test_groups": [{{"name":"Control","description":"..."}},{{"name":"Treatment","description":"..."}}],
   "metrics": ["metric1","metric2"], "duration_days": 30,
   "success_criteria": {{"primary":"...","secondary":"..."}},
   "risk": "..."}}]

Each experiment must be specific, measurable, and ethical."""
    try:
        result = model_ask(prompt, json_mode=True)
        if result:
            data = json.loads(result) if isinstance(result, str) else result
            return data if isinstance(data, list) else [data]
    except Exception:
        pass
    return []


def get_active_experiments(state: dict = None) -> list:
    """Return list of currently running experiments from state."""
    if state:
        return state.get("experiments", [])
    return []


def update_experiment_status(experiment: dict, status: str, state: dict = None):
    """Update experiment status (launched, running, completed, failed)."""
    exp = dict(experiment)
    exp["status"] = status
    exp["updated_at"] = datetime.now().isoformat()
    if state:
        state.setdefault("experiments", [])
        for i, e in enumerate(state["experiments"]):
            if e.get("name") == experiment.get("name"):
                state["experiments"][i] = exp
                return
        state["experiments"].append(exp)
