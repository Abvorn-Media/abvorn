"""Emotional Arc Score (EAS) — tracks sentiment trajectory over product lifecycle.

EAS = Σ(S_t * W_t) / Σ W_t

The curve shape tells the real story:
- Starts high, drops → 'Honeymoon Phase' (impulse appeal fades)
- Starts low, rises → 'Grower' (learns to love it)
- Flat → 'Consistent' (what you see is what you get)
"""
from datetime import datetime


def emotional_arc_score(sentiment_history: list, recency_decay: float = 0.9) -> dict:
    """Compute EAS from sentiment time-series.

    Args:
        sentiment_history: list of (sentiment_score: float 0-10, timestamp: str/datetime)
        recency_decay: weight multiplier per time unit (lower = more recency bias)

    Returns:
        dict with eas, curve_shape, segments
    """
    if not sentiment_history:
        return {"eas": 5.0, "curve_shape": "unknown", "segments": []}

    parsed = []
    for score, ts in sentiment_history:
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except ValueError:
                ts = datetime.now()
        parsed.append((float(score), ts))

    parsed.sort(key=lambda x: x[1])

    total_weight = 0.0
    weighted_sum = 0.0
    segments = []
    weights = []

    for i, (score, ts) in enumerate(parsed):
        w = recency_decay ** (len(parsed) - 1 - i)
        weighted_sum += score * w
        total_weight += w
        weights.append(w)
        segments.append({"position": i, "score": score, "weight": round(w, 3)})

    eas = round(weighted_sum / total_weight, 2) if total_weight > 0 else 5.0

    early = sum(s for s, _ in parsed[:max(1, len(parsed)//3)]) / max(1, len(parsed)//3)
    late = sum(s for s, _ in parsed[-max(1, len(parsed)//3):]) / max(1, len(parsed)//3)

    delta = late - early
    if delta > 1.0:
        shape = "grower"
        shape_label = "Grower (Improves Over Time)"
    elif delta < -1.0:
        shape = "honeymoon"
        shape_label = "Honeymoon Phase (Fades Over Time)"
    else:
        shape = "consistent"
        shape_label = "Consistent (Stable Performance)"

    return {
        "eas": eas,
        "shape": shape,
        "shape_label": shape_label,
        "segments": segments,
        "early_avg": round(early, 2),
        "late_avg": round(late, 2),
        "delta": round(delta, 2),
    }


def eas_from_product_data(product_data: dict) -> dict:
    """Convenience: generate a synthetic sentiment history from product data when no real history exists.

    Uses features count and price as rough sentiment proxies across a simulated timeline.
    """
    features = product_data.get("features", [])
    price_str = str(product_data.get("price", "0"))
    import re
    m = re.search(r"(\d+\.?\d*)", price_str.replace(",", ""))
    price = float(m.group(1)) if m else 0

    from datetime import timedelta
    now = datetime.now()
    scores = []
    base_score = min(9.0, max(4.0, 6.0 + len(features) * 0.3 - (price / 500)))
    for month_back in [12, 9, 6, 3, 1, 0]:
        jitter = (month_back % 3) * 0.3
        s = min(10.0, max(1.0, base_score + jitter - month_back * 0.05))
        scores.append((s, now - timedelta(days=month_back * 30)))

    return emotional_arc_score(scores)
