"""Questioner Agent — generates hypotheses from formula outputs and data anomalies.

Inputs: formula outputs (CI, EAS, SSI, RV), product data, anomalies
Outputs: structured questions with hypotheses and proposed experiments

No API required. Uses rule-based question templates when no model available.
"""


def questioner_agent(formula_outputs: dict, product_data: dict = None,
                     model_ask=None) -> list:
    """Generate 'what if' questions from formula results.

    Args:
        formula_outputs: dict with keys 'ci', 'eas', 'ssi', 'rv' — each containing formula result dicts
        product_data: optional product dict for context
        model_ask: optional callable(prompt) for AI-powered question generation

    Returns:
        list of question dicts: {question, hypothesis, experiment_idea, source_formula, severity}
    """
    questions = []

    q = _from_ci(formula_outputs.get("ci"))
    if q:
        questions.extend(q)

    q = _from_eas(formula_outputs.get("eas"))
    if q:
        questions.extend(q)

    q = _from_ssi(formula_outputs.get("ssi"))
    if q:
        questions.extend(q)

    q = _from_rv(formula_outputs.get("rv"))
    if q:
        questions.extend(q)

    q = _from_anomalies(formula_outputs, product_data)
    if q:
        questions.extend(q)

    if model_ask and (product_data or formula_outputs):
        ai_q = _generate_with_model(formula_outputs, product_data, model_ask)
        if ai_q:
            questions.extend(ai_q)

    return questions


def _from_ci(ci_result: dict) -> list:
    if not ci_result:
        return []
    ci = ci_result.get("ci", 0)
    classification = ci_result.get("classification", {})
    label = classification.get("label", "")
    if label == "Underrated":
        return [{
            "question": f"What if this product's low rating is caused by something other than the product itself (e.g., brand bias, poor marketing)?",
            "hypothesis": "The gap between Verdict score and sentiment is driven by perception, not performance.",
            "experiment_idea": "A/B test product presentation: same specs, different brand framing → measure sentiment shift.",
            "source_formula": "ci",
            "severity": "high" if abs(ci) > 0.5 else "medium",
        }]
    if label == "Overrated":
        return [{
            "question": f"What if users are inflating ratings because of brand loyalty or social pressure?",
            "hypothesis": "High sentiment doesn't reflect real satisfaction — it reflects identity signaling.",
            "experiment_idea": "Show anonymous vs identified review prompts → measure rating difference.",
            "source_formula": "ci",
            "severity": "high" if abs(ci) > 0.5 else "medium",
        }]
    return []


def _from_eas(eas_result: dict) -> list:
    if not eas_result:
        return []
    shape = eas_result.get("shape", "")
    if shape == "honeymoon":
        return [{
            "question": "What if the honeymoon effect is hiding a fundamental flaw that only emerges after 30 days?",
            "hypothesis": "Products with steep honeymoon curves have a specific failure point that triggers disappointment.",
            "experiment_idea": "Target 30-day post-purchase users with a satisfaction survey → identify the drop-off moment.",
            "source_formula": "eas",
            "severity": "high",
        }]
    if shape == "grower":
        return [{
            "question": "What if 'grower' products are actually just products with bad onboarding that users eventually learn to work around?",
            "hypothesis": "The learning curve is mistaken for product improvement — users adapt to flaws.",
            "experiment_idea": "Compare satisfaction between guided-setup and self-setup cohorts.",
            "source_formula": "eas",
            "severity": "medium",
        }]
    return []


def _from_ssi(ssi_result: dict) -> list:
    if not ssi_result or not isinstance(ssi_result, dict):
        return []
    classification = ssi_result.get("classification", {})
    if isinstance(classification, str):
        classification = {"label": classification}
    label = classification.get("label", "") if isinstance(classification, dict) else ""
    features = ssi_result.get("features", [])
    blind_spots = [f for f in features if f.get("gap", 0) < -3]
    noise = [f for f in features if f.get("gap", 0) > 3]

    qs = []
    if blind_spots:
        names = ", ".join(f["feature"] for f in blind_spots[:2])
        qs.append({
            "question": f"What if {names} is actually the #1 decision factor, but nobody talks about it?",
            "hypothesis": f"The silent signal around {names} represents an unmet need that drives purchasing decisions.",
            "experiment_idea": f"Feature {blind_spots[0]['feature']} prominently in a headline → measure CTR vs standard headline.",
            "source_formula": "ssi",
            "severity": "high",
        })
    if noise:
        names = ", ".join(f["feature"] for f in noise[:2])
        qs.append({
            "question": f"What if the focus on {names} is actually a distraction from what really matters?",
            "hypothesis": f"Market conversation is dominated by {names} because it's easy to measure, not because it predicts satisfaction.",
            "experiment_idea": f"Remove {noise[0]['feature']} from product comparison table → measure if decision quality changes.",
            "source_formula": "ssi",
            "severity": "medium",
        })
    return qs


def _from_rv(rv_result: dict) -> list:
    if not rv_result:
        return []
    label = rv_result.get("classification", {}).get("label", "")
    if label == "Impulse Regret":
        return [{
            "question": "What if showing the Regret Probability Score BEFORE purchase converts fewer buyers but reduces returns?",
            "hypothesis": "RPS-aware buyers make better decisions, resulting in higher long-term satisfaction despite lower conversion.",
            "experiment_idea": "A/B test: 50% see RPS widget, 50% don't. Measure conversion rate AND return rate over 90 days.",
            "source_formula": "rv",
            "severity": "high",
        }]
    if label == "Growing Satisfaction":
        return [{
            "question": "What if products with growing satisfaction curves should have a 'tip' section for getting the most out of them?",
            "hypothesis": "Users who receive usage tips experience faster satisfaction growth.",
            "experiment_idea": "A/B test: add 'getting started' section vs standard layout → measure satisfaction at 30 days.",
            "source_formula": "rv",
            "severity": "medium",
        }]
    return []


def _from_anomalies(formula_outputs: dict, product_data: dict) -> list:
    """Detect cross-formula anomalies for deeper questions."""
    qs = []
    ci = formula_outputs.get("ci", {})
    eas = formula_outputs.get("eas", {})
    rv = formula_outputs.get("rv", {})

    ci_label = ci.get("classification", {}).get("label", "")
    eas_shape = eas.get("shape", "")
    rv_label = rv.get("classification", {}).get("label", "")

    if ci_label == "Overrated" and eas_shape == "honeymoon":
        qs.append({
            "question": "What if overrated products always have honeymoon curves because initial hype masks long-term flaws?",
            "hypothesis": "CI and EAS are correlated — overrated products degrade faster.",
            "experiment_idea": "Track CI + EAS together for new products. If both trigger, flag as 'watch list'.",
            "source_formula": "ci+eas",
            "severity": "medium",
        })
    if rv_label == "Impulse Regret" and ci_label == "Overrated":
        qs.append({
            "question": "What if impulse regret is concentrated in overrated products? RPS becomes a leading indicator of CI collapse.",
            "hypothesis": "High RV predicts future CI negativity — regret velocity precedes reputation damage.",
            "experiment_idea": "Build a predictive model: RV → CI change over 6 months.",
            "source_formula": "rv+ci",
            "severity": "high",
        })
    return qs


def _generate_with_model(formula_outputs: dict, product_data: dict, model_ask) -> list:
    """Use model to generate additional questions beyond templates."""
    import json

    ci = formula_outputs.get("ci", {})
    eas = formula_outputs.get("eas", {})
    ssi = formula_outputs.get("ssi", {})
    rv = formula_outputs.get("rv", {})

    prompt = f"""You are the Questioner Agent in a decision intelligence system.
Analyze these formula outputs and generate 1-2 novel "what if" questions.

CI: {json.dumps(ci.get('classification', {}))}
EAS shape: {eas.get('shape', 'unknown')} (early={eas.get('early_avg')}, late={eas.get('late_avg')})
SSI: {json.dumps(ssi.get('classification', {}))}
RV: {rv.get('classification', {}).get('label', 'unknown')}

Product: {json.dumps(product_data, default=str)[:500] if product_data else 'N/A'}

Return a JSON array of objects:
[{{"question": "...", "hypothesis": "...", "experiment_idea": "...", "source_formula": "ai", "severity": "high|medium|low"}}]

Ask questions that challenge our assumptions. What if we're measuring the wrong thing?
What if there's a hidden variable we're not tracking?"""

    try:
        result = model_ask(prompt, json_mode=True)
        if result:
            data = json.loads(result) if isinstance(result, str) else result
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
    except Exception:
        pass
    return []
