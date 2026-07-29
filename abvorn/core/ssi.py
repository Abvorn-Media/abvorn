"""Silent Signal Index (SSI) — measures gap between what people talk about and what matters.

SSI = Σ(M_i - E_i) / N

SSI >  0.5 → Noise (people talk about things that don't matter)
SSI < -0.5 → Blind spot (people ignore things that matter)
SSI ≈ 0    → Alignment (discussion matches importance)
"""


def silent_signal_index(mention_frequencies: dict, expert_importances: dict) -> dict:
    """Compute SSI from mention frequency vs expert-rated importance.

    Args:
        mention_frequencies: dict of feature_label -> mention_count (raw)
        expert_importances: dict of feature_label -> importance_score (0-10)

    Returns:
        dict with ssi, classification, per_feature breakdown
    """
    if not mention_frequencies or not expert_importances:
        return {"ssi": 0.0, "classification": "no_data", "features": []}

    all_keys = set(mention_frequencies) | set(expert_importances)
    total_freq = sum(mention_frequencies.values()) or 1

    diffs = []
    feature_details = []

    for key in sorted(all_keys):
        m = mention_frequencies.get(key, 0) / total_freq  # normalized 0-1
        # Scale mention frequency to 0-10 range for comparison
        m_scaled = m * 10
        e = expert_importances.get(key, 5.0)
        diff = m_scaled - e
        diffs.append(diff)
        feature_details.append({
            "feature": key,
            "mention_frequency_norm": round(m_scaled, 2),
            "expert_importance": e,
            "gap": round(diff, 2),
            "interpretation": _interpret_gap(diff),
        })

    ssi = round(sum(diffs) / len(diffs), 3) if diffs else 0.0
    return {
        "ssi": ssi,
        "classification": _classify_ssi(ssi),
        "features": feature_details,
    }


def ssi_from_category_weights(mention_frequencies: dict, niche_weights: dict) -> dict:
    """Convenience: compute SSI using Verdict Engine category weights as expert importance."""
    expert = {}
    for cat, cfg in niche_weights.items():
        expert[cfg["label"]] = round(cfg["weight"] * 10, 1)
    return silent_signal_index(mention_frequencies, expert)


def estimate_mention_frequencies(product_data: dict) -> dict:
    """Estimate mention frequencies from product features and description."""
    text = " ".join(product_data.get("features", []))
    text += " " + product_data.get("description", "")
    text += " " + product_data.get("name", "")
    text = text.lower()

    patterns = {
        "Sound Quality": ["sound", "audio", "bass", "treble", "clarity", "noise cancelling", "anc"],
        "Battery Life": ["battery", "battery life", "hours", "playback", "runtime"],
        "Comfort & Fit": ["comfort", "fit", "lightweight", "ergonomic", "cushion", "adjustable"],
        "Features & Tech": ["feature", "bluetooth", "wireless", "app", "smart", "connectivity"],
        "Value for Money": ["value", "price", "affordable", "budget", "cheap", "expensive", "worth"],
        "Performance": ["fast", "speed", "performance", "powerful", "responsive"],
        "Build Quality": ["build", "premium", "durable", "aluminum", "metal", "plastic"],
        "Design": ["design", "sleek", "minimal", "beautiful", "modern", "style"],
        "Ease of Use": ["easy", "simple", "intuitive", "setup", "plug"],
        "Reliability": ["reliable", "durable", "long lasting", "warranty", "solid"],
        "Accuracy": ["accurate", "precision", "exact", "sensor", "tracking"],
        "Compatibility": ["compatible", "works with", "alexa", "google", "homekit", "ios", "android"],
    }

    frequencies = {}
    for label, keywords in patterns.items():
        count = sum(text.count(kw) for kw in keywords)
        if count > 0:
            frequencies[label] = count

    return frequencies


def _interpret_gap(gap: float) -> str:
    if gap > 3:
        return "Over-discussed — people talk about this more than it matters"
    if gap > 1:
        return "Slightly over-discussed"
    if gap < -3:
        return "Blind spot — people ignore this despite its importance"
    if gap < -1:
        return "Slightly under-discussed"
    return "Balanced"


def _classify_ssi(ssi: float) -> dict:
    if ssi > 0.5:
        return {"label": "Noisy", "color": "#d4633e", "description": "Conversation is dominated by low-importance factors."}
    if ssi > 0.2:
        return {"label": "Slightly Noisy", "color": "#e8a040", "description": "Some over-discussion of minor features."}
    if ssi < -0.5:
        return {"label": "Blind Spot", "color": "#c0392b", "description": "Important factors are being ignored."}
    if ssi < -0.2:
        return {"label": "Slight Blind Spot", "color": "#d4a03e", "description": "Some important factors are under-discussed."}
    return {"label": "Aligned", "color": "#3a8a5c", "description": "Discussion matches importance."}
