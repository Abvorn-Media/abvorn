"""Regret Probability Score (RPS) — predictive model that estimates
the probability a specific user will regret buying a specific product.

No accounts required. Preferences are inferred from browsing behavior
and stored in localStorage. The model runs client-side for zero latency.
"""

# ── Preference-to-score dimension mapping ──────────────────────────────
# Maps user preference keys to Verdict Engine score labels.
# This is the "Rosetta Stone" that lets us compare what users want
# against what products deliver.
PREFERENCE_MAP = {
    "sound_quality":    "Sound Quality",
    "battery_life":     "Battery Life",
    "comfort":          "Comfort & Fit",
    "features":         "Features & Tech",
    "value":            "Value for Money",
    "performance":      "Performance",
    "build_quality":    "Build Quality",
    "ease_of_use":      "Ease of Use",
    "design":           "Design",
    "reliability":      "Reliability",
    "accuracy":         "Accuracy",
    "compatibility":    "Compatibility",
}

# Default preference profile (used when user has no history)
DEFAULT_PREFS = {
    "sound_quality": 5.0,
    "battery_life": 5.0,
    "comfort": 5.0,
    "features": 5.0,
    "value": 5.0,
}

RPS_THRESHOLDS = [
    (0.0, "Low Regret Risk", "#3a8a5c", "This product aligns well with your preferences."),
    (0.3, "Moderate Regret Risk", "#d4a03e", "Some of your priorities don't match this product."),
    (0.6, "High Regret Risk", "#d4633e", "This product may not be right for you."),
    (0.8, "Very High Regret Risk", "#c0392b", "Based on your preferences, this is likely the wrong choice."),
]


def calculate_regret(user_prefs: dict, product_scores: dict, niche_slug: str = "") -> dict:
    """Calculate the regret probability for a user-product pair.

    Args:
        user_prefs: dict of preference_key -> importance (0-10)
        product_scores: dict of score_label -> score (0-10), as returned by Verdict Engine

    Returns:
        dict with regret_probability, alignment_score, reasons, severity
    """
    if not user_prefs:
        user_prefs = DEFAULT_PREFS

    if not product_scores:
        return _empty_result("No score data available for this product.")

    alignment = _calculate_alignment(user_prefs, product_scores)
    regret_probability = max(0.0, min(1.0, 1.0 - alignment))
    severity = _classify_regret(regret_probability)

    return {
        "regret_probability": round(regret_probability * 100, 1),
        "alignment_score": round(alignment, 2),
        "severity": severity,
        "reasons": _generate_reasons(user_prefs, product_scores),
        "good_matches": _good_matches(user_prefs, product_scores),
        "poor_matches": _poor_matches(user_prefs, product_scores),
    }


def rank_alternatives(user_prefs: dict, products: list, niche_slug: str = "") -> list:
    """Rank alternative products by regret risk (lowest first).

    Args:
        user_prefs: dict of preference_key -> importance
        products: list of product dicts, each with a "scores" key from Verdict Engine

    Returns:
        list of (product_name, regret_dict) sorted by regret_probability ascending
    """
    if not user_prefs:
        user_prefs = DEFAULT_PREFS

    scored = []
    for prod in products:
        scores = prod.get("scores", prod.get("verdict", {}).get("breakdown", {}))
        if scores:
            regret = calculate_regret(user_prefs, scores, niche_slug)
            scored.append((prod.get("name", "Unknown"), regret, prod))

    scored.sort(key=lambda x: x[1]["regret_probability"])
    return scored


def prefs_from_signals(signals: list) -> dict:
    """Infer preference profile from browsing signals.

    signals: list of dicts with keys:
        - category: str (e.g. "battery_life", "sound_quality")
        - weight: float (how strong the signal is, 0-10)
        - type: "click" | "view" | "search" | "compare"
    """
    prefs = dict(DEFAULT_PREFS)
    counts = {k: 0 for k in prefs}

    for s in signals:
        cat = s.get("category", "")
        if cat in prefs:
            w = max(0.0, min(10.0, float(s.get("weight", 5))))
            # Amplify based on signal type
            type_mult = {"click": 1.5, "view": 0.8, "search": 2.0, "compare": 1.2}
            w *= type_mult.get(s.get("type", "view"), 1.0)
            prefs[cat] += w
            counts[cat] += 1

    # Average by signal count
    for k in prefs:
        if counts[k] > 0:
            prefs[k] = round(min(10.0, prefs[k] / counts[k]), 1)
        else:
            prefs[k] = 5.0

    return prefs


def _calculate_alignment(user_prefs: dict, product_scores: dict) -> float:
    """Weighted alignment between user preferences and product scores.

    1.0 = perfect match. 0.0 = complete mismatch.
    """
    total_weight = 0.0
    weighted_sum = 0.0

    for pref_key, importance in user_prefs.items():
        importance = max(0.0, min(10.0, float(importance)))
        score_label = PREFERENCE_MAP.get(pref_key)
        if not score_label or score_label not in product_scores:
            continue

        product_val = float(product_scores[score_label])
        # Alignment = 1 - |pref - product| / 10 (normalized difference)
        diff = abs(importance - product_val) / 10.0
        alignment = 1.0 - diff

        weighted_sum += alignment * importance
        total_weight += importance

    if total_weight == 0:
        return 0.5  # Neutral alignment when no preferences

    return weighted_sum / total_weight


def _generate_reasons(user_prefs: dict, product_scores: dict) -> list:
    """Generate human-readable reasons why user might regret this purchase."""
    reasons = []

    for pref_key, importance in sorted(user_prefs.items(), key=lambda x: -x[1]):
        if importance < 3:
            continue  # Skip low-importance preferences

        score_label = PREFERENCE_MAP.get(pref_key)
        if not score_label or score_label not in product_scores:
            continue

        product_val = float(product_scores[score_label])
        diff = importance - product_val

        if diff > 3:
            reasons.append({
                "type": "mismatch",
                "preference": pref_key,
                "importance": importance,
                "product_score": product_val,
                "message": f"You prioritize {_pref_name(pref_key)} ({importance}/10), but this product scores {product_val}/10.",
            })
        elif diff < -3:
            reasons.append({
                "type": "surplus",
                "preference": pref_key,
                "importance": importance,
                "product_score": product_val,
                "message": f"The product excels at {_pref_name(pref_key)} ({product_val}/10), which you care less about ({importance}/10).",
            })

    return reasons[:4]  # Max 4 reasons


def _good_matches(user_prefs: dict, product_scores: dict) -> list:
    good = []
    for pref_key, importance in sorted(user_prefs.items(), key=lambda x: -x[1]):
        if importance < 5:
            continue
        score_label = PREFERENCE_MAP.get(pref_key)
        if not score_label or score_label not in product_scores:
            continue
        product_val = float(product_scores[score_label])
        if abs(importance - product_val) <= 2:
            good.append({
                "label": _pref_name(pref_key),
                "importance": importance,
                "score": product_val,
                "icon": "check",
            })
    return good[:3]


def _poor_matches(user_prefs: dict, product_scores: dict) -> list:
    poor = []
    for pref_key, importance in sorted(user_prefs.items(), key=lambda x: -x[1]):
        if importance < 5:
            continue
        score_label = PREFERENCE_MAP.get(pref_key)
        if not score_label or score_label not in product_scores:
            continue
        product_val = float(product_scores[score_label])
        if abs(importance - product_val) > 2:
            poor.append({
                "label": _pref_name(pref_key),
                "importance": importance,
                "score": product_val,
                "icon": "x",
            })
    return poor[:3]


def _classify_regret(prob: float) -> dict:
    for threshold, label, color, tip in RPS_THRESHOLDS:
        if prob >= threshold:
            return {"label": label, "color": color, "tip": tip}
    return {"label": "Low Regret Risk", "color": "#3a8a5c", "tip": "Good alignment."}


def _pref_name(key: str) -> str:
    return key.replace("_", " ").title()


def _empty_result(message: str) -> dict:
    return {
        "regret_probability": 50.0,
        "alignment_score": 0.5,
        "severity": {"label": "Unknown", "color": "#9e9690", "tip": message},
        "reasons": [],
        "good_matches": [],
        "poor_matches": [],
    }
