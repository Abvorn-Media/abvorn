"""Abvorn Verdict Engine — proprietary scoring system.

This is our moat. Weights, categories, and logic are ours alone.
Every product gets an objective, data-driven score displayed on every review.
"""

import html as _html
import re

# ── Proprietary category weights per niche ──────────────────────────────
# Each category has a weight (sums to 1.0) and a display label.
CATEGORY_WEIGHTS = {
    "wireless-headphones": {
        "sound":      {"weight": 0.25, "label": "Sound Quality"},
        "comfort":    {"weight": 0.20, "label": "Comfort & Fit"},
        "battery":    {"weight": 0.15, "label": "Battery Life"},
        "features":   {"weight": 0.20, "label": "Features & Tech"},
        "value":      {"weight": 0.20, "label": "Value for Money"},
    },
    "wireless-earbuds": {
        "sound":      {"weight": 0.20, "label": "Sound Quality"},
        "fit":        {"weight": 0.20, "label": "Fit & Seal"},
        "battery":    {"weight": 0.15, "label": "Battery Life"},
        "features":   {"weight": 0.20, "label": "Features & Tech"},
        "value":      {"weight": 0.25, "label": "Value for Money"},
    },
    "gaming-mice": {
        "sensor":     {"weight": 0.25, "label": "Sensor Performance"},
        "build":      {"weight": 0.20, "label": "Build Quality"},
        "software":   {"weight": 0.15, "label": "Software"},
        "comfort":    {"weight": 0.20, "label": "Comfort & Grip"},
        "value":      {"weight": 0.20, "label": "Value for Money"},
    },
    "mechanical-keyboards": {
        "build":      {"weight": 0.20, "label": "Build Quality"},
        "switches":   {"weight": 0.25, "label": "Switch Quality"},
        "features":   {"weight": 0.20, "label": "Features"},
        "design":     {"weight": 0.15, "label": "Design"},
        "value":      {"weight": 0.20, "label": "Value for Money"},
    },
    "4k-monitors": {
        "color":      {"weight": 0.25, "label": "Color Accuracy"},
        "motion":     {"weight": 0.20, "label": "Motion Handling"},
        "build":      {"weight": 0.15, "label": "Build & Stand"},
        "features":   {"weight": 0.20, "label": "Connectivity & Features"},
        "value":      {"weight": 0.20, "label": "Value for Money"},
    },
    "laptops": {
        "performance": {"weight": 0.25, "label": "Performance"},
        "display":     {"weight": 0.15, "label": "Display"},
        "battery":     {"weight": 0.20, "label": "Battery Life"},
        "build":       {"weight": 0.20, "label": "Build & Portability"},
        "value":       {"weight": 0.20, "label": "Value for Money"},
    },
    "streaming-devices": {
        "speed":      {"weight": 0.25, "label": "Performance & Speed"},
        "interface":  {"weight": 0.20, "label": "Interface & Ease of Use"},
        "content":    {"weight": 0.20, "label": "Content Availability"},
        "features":   {"weight": 0.20, "label": "Features & Voice"},
        "value":      {"weight": 0.15, "label": "Value for Money"},
    },
    "fitness-trackers": {
        "accuracy":   {"weight": 0.25, "label": "Accuracy"},
        "battery":    {"weight": 0.20, "label": "Battery Life"},
        "features":   {"weight": 0.20, "label": "Health Features"},
        "comfort":    {"weight": 0.15, "label": "Comfort & Wearability"},
        "value":      {"weight": 0.20, "label": "Value for Money"},
    },
    "webcams": {
        "video":      {"weight": 0.30, "label": "Video Quality"},
        "audio":      {"weight": 0.20, "label": "Audio Quality"},
        "features":   {"weight": 0.20, "label": "Features & Software"},
        "build":      {"weight": 0.10, "label": "Build Quality"},
        "value":      {"weight": 0.20, "label": "Value for Money"},
    },
    "smart-home": {
        "reliability": {"weight": 0.25, "label": "Reliability"},
        "ease":        {"weight": 0.20, "label": "Ease of Use"},
        "features":    {"weight": 0.20, "label": "Features"},
        "compatibility":{"weight": 0.20, "label": "Compatibility"},
        "value":       {"weight": 0.15, "label": "Value for Money"},
    },
}

FALLBACK_WEIGHTS = {
    "quality":    {"weight": 0.25, "label": "Quality"},
    "features":   {"weight": 0.20, "label": "Features"},
    "ease":       {"weight": 0.20, "label": "Ease of Use"},
    "design":     {"weight": 0.15, "label": "Design"},
    "value":      {"weight": 0.20, "label": "Value"},
}

LABELS = [
    (9.0, "Exceptional"),
    (8.0, "Excellent"),
    (7.0, "Good"),
    (6.0, "Average"),
    (0.0, "Poor"),
]

VERDICT_HTML = """<div class="abvorn-verdict">
<div class="av-badge">Abvorn Verdict</div>
<div class="av-score-row">
  <div class="av-score">
    <span class="av-number">{overall}</span>
    <span class="av-outof">/10</span>
  </div>
  <div class="av-label-row">
    <h3 class="av-product">{product_name}</h3>
    <span class="av-label">{label}</span>
  </div>
</div>
<div class="av-breakdown">
{breakdown_bars}
</div>
<div class="av-summary">{summary}</div>
<div class="av-cta">
  <a class="buy-btn" href="{affiliate_url}" target="_blank" rel="sponsored">Check Price on Amazon →</a>
</div>
</div>"""


class AbvornVerdictEngine:
    """Proprietary scoring engine. Our IP.

    Supports hot-reloaded weights from `ndc_weight_overrides` dict,
    enabling the Learner Agent to evolve scoring criteria across cycles.
    """

    def __init__(self, weight_overrides: dict = None):
        self._weights_cache = {}
        self._overrides = weight_overrides or {}

    def _get_weights(self, niche_slug: str) -> dict:
        if niche_slug not in self._weights_cache:
            base = CATEGORY_WEIGHTS.get(niche_slug, FALLBACK_WEIGHTS)
            # Apply Learner-driven overrides if present
            override = self._overrides.get(niche_slug)
            if override:
                merged = {}
                for cat, cfg in base.items():
                    merged[cat] = dict(cfg)
                    if cat in override:
                        merged[cat]["weight"] = override[cat]
                self._weights_cache[niche_slug] = merged
            else:
                self._weights_cache[niche_slug] = base
        return self._weights_cache[niche_slug]

    @staticmethod
    def apply_learner_weight_update(overrides: dict, niche_slug: str, category: str, new_weight: float) -> dict:
        """Return updated overrides dict with a single weight change.

        Called by the Learner Agent to evolve scoring criteria.
        """
        overrides = dict(overrides)
        overrides.setdefault(niche_slug, {})
        overrides[niche_slug][category] = max(0.05, min(0.50, new_weight))
        return overrides

    def score_product(self, niche_slug: str, product_data: dict) -> dict:
        """Compute the Abvorn Verdict score for a product.

        product_data can include:
          - name, price, description, features, scores (dict override per category)
          - specs dict with keys like battery, weight, rating
        """
        weights = self._get_weights(niche_slug)
        scores = {}

        explicit = product_data.get("scores")
        if explicit and isinstance(explicit, dict):
            for cat in weights:
                val = explicit.get(cat)
                scores[cat] = max(0.0, min(10.0, float(val))) if val is not None else self._estimate(product_data, cat)
        else:
            for cat in weights:
                scores[cat] = max(0.0, min(10.0, self._estimate(product_data, cat)))

        total = sum(scores.get(cat, 0.0) * weights[cat]["weight"] for cat in weights)
        label = next(t for t in LABELS if total >= t[0])[1]

        best = max(weights, key=lambda c: scores.get(c, 0))
        worst = min(weights, key=lambda c: scores.get(c, 0))
        summary = self._summary(product_data, weights[best]["label"], weights[worst]["label"])

        breakdown = {}
        for cat in weights:
            breakdown[weights[cat]["label"]] = round(scores.get(cat, 0.0), 1)

        return {
            "overall": round(total, 1),
            "breakdown": breakdown,
            "label": label,
            "summary": summary,
        }

    def _estimate(self, data: dict, category: str) -> float:
        """Rule-based estimate when no explicit score is given."""
        name = (data.get("name", "") + " " + data.get("description", "")).lower()
        price_str = str(data.get("price", ""))
        features = [f.lower() for f in data.get("features", [])]
        features_text = " ".join(features)
        full_text = name + " " + features_text

        # Extract numeric price
        price_match = re.search(r"(\d+\.?\d*)", price_str.replace(",", ""))
        price = float(price_match.group(1)) if price_match else 0.0

        boost = 0.0

        # Category-specific heuristics
        if category == "value":
            if price == 0:
                boost = 5.0
            elif price < 50:
                boost = 8.0
            elif price < 100:
                boost = 7.0
            elif price < 200:
                boost = 6.0
            elif price < 500:
                boost = 5.0
            else:
                boost = 4.0
            # premium brands get negative value boost
            for word in ["premium", "pro", "ultra"]:
                if word in name:
                    boost -= 0.5
            return min(10.0, max(1.0, boost))

        if category == "battery":
            # Look for battery life context, not quick-charge numbers
            battery_match = re.search(r"(?:battery|playback|talk)\s*(?:life|time)?\s*(?:of|up\s*to)?\s*(\d+)\s*(?:hour|hr)", full_text)
            if battery_match:
                val = float(battery_match.group(1))
                return min(10.0, val / 4)
            # Fallback: look for standalone "X hours" near battery context
            fallback = re.search(r"(\d+)\s*(?:hour|hr)\s*(?:battery|playback|life|runtime)", full_text)
            if fallback:
                val = float(fallback.group(1))
                return min(10.0, val / 4)
            return 7.5

        if category == "comfort":
            good = ["lightweight", "ergonomic", "adjustable", "breathable", "cushion"]
            bad = ["heavy", "bulky", "tight", "stiff"]
            boost += sum(0.5 for w in good if w in full_text)
            boost -= sum(0.5 for w in bad if w in full_text)
            return max(3.0, min(10.0, 7.0 + boost))

        if category in ("sound", "video", "color", "accuracy"):
            good = ["crystal clear", "high res", "high resolution", "vivid", "sharp", "accurate", "4k"]
            boost += sum(0.5 for w in good if w in full_text)
            return max(3.0, min(10.0, 7.5 + boost))

        if category in ("features", "software", "connectivity"):
            count = len(features)
            return min(10.0, 5.0 + count * 0.8)

        if category in ("build", "quality", "reliability"):
            good = ["premium", "durable", "solid", "aluminum", "metal", "reinforced"]
            boost += sum(0.5 for w in good if w in full_text)
            return max(3.0, min(10.0, 7.0 + boost))

        if category in ("performance", "speed", "motion"):
            good = ["fast", "responsive", "low latency", "high refresh", "instant", "snappy"]
            boost += sum(0.5 for w in good if w in full_text)
            return max(3.0, min(10.0, 7.0 + boost))

        if category in ("design", "interface", "ease"):
            good = ["sleek", "minimal", "intuitive", "clean", "beautiful", "modern", "simple"]
            boost += sum(0.4 for w in good if w in full_text)
            return max(3.0, min(10.0, 7.0 + boost))

        if category in ("compatibility", "content"):
            good = ["alexa", "google", "homekit", "smartthings", "zigbee", "zwave", "works with"]
            boost += sum(0.6 for w in good if w in full_text)
            return max(3.0, min(10.0, 7.0 + boost))

        return 7.0

    def _summary(self, data: dict, best_label: str, worst_label: str) -> str:
        """One-sentence verdict summary."""
        name = clean_product_name(data.get("name", "This product"))
        return f"{name} excels in {best_label} but falls short on {worst_label}. Our view: {self._final_judgment(data, best_label)}"

    def _final_judgment(self, data: dict, best_label: str) -> str:
        name = (data.get("name", "") + " " + data.get("description", "")).lower()
        price_str = str(data.get("price", ""))
        price_match = re.search(r"(\d+\.?\d*)", price_str.replace(",", ""))
        price = float(price_match.group(1)) if price_match else 0.0

        if price > 500:
            return "A premium investment for those who demand the best."
        if price > 200:
            return "Serious performance at a serious price — worth it if you use it daily."
        if price > 80:
            return "Great mid-range value that punches above its weight."
        if "budget" in name or price < 40:
            return "The best bang for your buck — ideal if you're watching your wallet."
        return "Solid performance at a fair price. Easy recommendation."


def clean_product_name(name: str) -> str:
    """Clean a raw product name for display.

    Amazon titles sometimes contain HTML-encoded and doubled quote characters
    (e.g. `1.1&quot;&quot;`), which render as ugly `1.1""`. This normalises
    entities and collapses doubled quotes to a single inch-mark.
    """
    if not name:
        return name
    cleaned = _html.unescape(str(name))
    cleaned = cleaned.replace('""', '"')
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
    return cleaned


def render_verdict_card(verdict: dict, product_name: str, affiliate_url: str = "", detail_url: str = "") -> str:
    """Render verdict dict into the HTML verdict card."""
    bars = ""
    for label, score in verdict["breakdown"].items():
        pct = int(score / 10 * 100)
        bar_color = "#3a8a5c" if score >= 7.0 else "#d4633e"
        bars += f"""<div class="av-bar-row"><span class="av-bar-label">{label}</span><div class="av-bar-track"><div class="av-bar-fill" style="width:{pct}%;background:{bar_color}"></div></div><span class="av-bar-score">{score}</span></div>"""

    return VERDICT_HTML.format(
        overall=verdict["overall"],
        label=verdict["label"],
        product_name=_html.escape(clean_product_name(product_name), quote=True),
        summary=verdict["summary"],
        breakdown_bars=bars,
        affiliate_url=affiliate_url or "#",
        detail_url=detail_url or "#",
    )
