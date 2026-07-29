"""Contrarian Index (CI) — measures gap between objective Verdict score and subjective market sentiment.

CI = (V_score - S_avg) / S_avg

CI > 0.5  → Underrated (hidden gem)
CI < -0.5 → Overrated (hype > reality)
CI ≈ 0    → Correctly rated
"""


def contrarian_index(verdict_score: float, avg_sentiment: float) -> float:
    """Compute CI from Verdict Engine score and average sentiment."""
    if avg_sentiment <= 0:
        return 0.0
    return round((verdict_score - avg_sentiment) / avg_sentiment, 3)


def classify_ci(ci: float) -> dict:
    if ci > 0.5:
        return {"label": "Underrated", "color": "#3a8a5c", "description": "Product outperforms its reputation — a hidden gem.", "action": "Highlight in content as 'underrated pick'"}
    if ci > 0.2:
        return {"label": "Slightly Underrated", "color": "#6aab7a", "description": "Better than people think.", "action": "Emphasize strengths in comparison tables"}
    if ci < -0.5:
        return {"label": "Overrated", "color": "#c0392b", "description": "Hype exceeds actual performance — buyer beware.", "action": "Flag as 'overhyped' in verdict"}
    if ci < -0.2:
        return {"label": "Slightly Overrated", "color": "#d4633e", "description": "Reputation slightly ahead of reality.", "action": "Add honest caveat in review"}
    return {"label": "Correctly Rated", "color": "#9e9690", "description": "Market perception matches our assessment.", "action": "Standard placement"}


def ci_from_product(verdict_score: float, product_rating: float = None, features: list = None) -> dict:
    """Convenience: compute CI from product data. Uses rating as sentiment proxy."""
    if product_rating:
        avg_sentiment = product_rating / 5 * 10  # normalized to 0-10 scale
    else:
        avg_sentiment = 7.0  # default baseline
    ci = contrarian_index(verdict_score, avg_sentiment)
    classification = classify_ci(ci)
    return {
        "ci": ci,
        "verdict_score": verdict_score,
        "avg_sentiment": avg_sentiment,
        "classification": classification,
    }
