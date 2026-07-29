"""Regret Velocity (RV) — measures how fast regret sets in after purchase.

RV = ΔR / Δt

High RV  → 'Impulse regret' (regret hits fast — buyer's remorse)
Low RV   → 'Creeping regret' (regret builds slowly over time)
Negative RV → 'Growing satisfaction' (likes it more over time)

Units: regret probability percentage points per month.
"""


def regret_velocity(initial_regret: float, current_regret: float, months_elapsed: float) -> dict:
    """Compute RV from regret at two points in time.

    Args:
        initial_regret: regret_probability at purchase time (0-100)
        current_regret: regret_probability now (0-100)
        months_elapsed: time since purchase in months

    Returns:
        dict with rv, classification, interpretation
    """
    if months_elapsed <= 0:
        return {"rv": 0.0, "classification": "no_data"}

    delta_r = current_regret - initial_regret
    rv = round(delta_r / months_elapsed, 3)

    classification = _classify_rv(rv)
    interpretation = classification["description"]

    return {
        "rv": rv,
        "delta_regret": round(delta_r, 1),
        "initial_regret": initial_regret,
        "current_regret": current_regret,
        "months_elapsed": months_elapsed,
        "classification": classification,
        "interpretation": interpretation,
    }


def regret_velocity_from_rps(user_prefs: dict, product_scores: dict,
                              initial_prefs: dict = None, months_elapsed: float = 3.0) -> dict:
    """Convenience: compute RV from two RPS calculations at different times.

    Simulates regret velocity by comparing current prefs vs initial prefs.
    """
    from .rps import calculate_regret

    current = calculate_regret(user_prefs, product_scores)
    initial = calculate_regret(initial_prefs or {}, product_scores)

    return regret_velocity(
        initial_regret=initial["regret_probability"],
        current_regret=current["regret_probability"],
        months_elapsed=months_elapsed,
    )


def estimate_regret_velocity(product_data: dict, user_prefs: dict = None) -> dict:
    """Convenience: estimate RV from single product snapshot using price as proxy for time."""
    from .rps import calculate_regret, DEFAULT_PREFS

    prefs = user_prefs or DEFAULT_PREFS
    price_str = str(product_data.get("price", "0"))
    import re
    m = re.search(r"(\d+\.?\d*)", price_str.replace(",", ""))
    price = float(m.group(1)) if m else 0

    scores = product_data.get("scores", {})
    if not scores:
        from .verdict import AbvornVerdictEngine
        try:
            ve = AbvornVerdictEngine()
            verdict = ve.score_product(product_data.get("niche", ""), product_data)
            scores = verdict["breakdown"]
        except Exception:
            scores = {}

    current = calculate_regret(prefs, scores)

    optimistic_prefs = {k: v * 0.8 for k, v in prefs.items()}
    initial = calculate_regret(optimistic_prefs, scores)

    months = max(1.0, min(24.0, price / 50))
    return regret_velocity(initial["regret_probability"], current["regret_probability"], months)


def _classify_rv(rv: float) -> dict:
    if rv > 5:
        return {"label": "Impulse Regret", "severity": "high", "color": "#c0392b", "description": "Buyer's remorse hits fast — likely an impulse purchase that didn't deliver."}
    if rv > 2:
        return {"label": "Rapid Regret", "severity": "moderate", "color": "#d4633e", "description": "Regret sets in within weeks. The product fails to meet expectations quickly."}
    if rv > 0.5:
        return {"label": "Creeping Regret", "severity": "low", "color": "#d4a03e", "description": "Satisfaction erodes slowly over time. Small annoyances compound."}
    if rv < -0.5:
        return {"label": "Growing Satisfaction", "severity": "positive", "color": "#3a8a5c", "description": "The product gets better with age — users learn to appreciate it more."}
    if rv < 0:
        return {"label": "Mild Improvement", "severity": "positive", "color": "#6aab7a", "description": "Slight upward trend in satisfaction over time."}
    return {"label": "Stable", "severity": "neutral", "color": "#9e9690", "description": "Regret probability holds steady. What you see is what you get."}
