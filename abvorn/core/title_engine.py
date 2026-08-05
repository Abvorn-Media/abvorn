"""title_engine.py — Oliver Henry scroll-stopping title engine.

Generates curiosity-driven review titles using the formula:

    [Person] + [conflict] → showed them [X] → they changed their mind

The engine works fully offline: it fills each template from the carousel
payload's real data (product name, verdict, breakdown, price, category) and
scores every variant with a base impact weight plus a learned bonus from the
performance history. No LLM call is required to produce variants, so it is
deterministic and unit-testable; the Colosseum Creator still writes the final
platform hook, but it now drafts from these variants.

The performance loop: `record_performance` logs wins per template + platform
and raises the learned weight for that pair, so the engine drifts toward the
templates that actually stop the scroll. History is persisted to a JSON file
and capped to keep the file small.

Usage:
    from abvorn.core.title_engine import get_title_engine
    engine = get_title_engine()
    variants = engine.generate_titles(carousel, platform="tiktok", count=5)
    engine.record_performance(platform="tiktok", template=variants[0]["template"], metric=0.031)
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("abvorn.title_engine")

# Template id -> (title template, base impact 0-1, which platforms it suits best)
# Base impact encodes the Oliver Henry intuition: templates that pair a named
# person with a concrete conflict score higher than generic question hooks.
TEMPLATES: Dict[str, Dict[str, Any]] = {
    "friend_proved_wrong": {
        "template": "My [person] said [product] was [criticism]... until I [action]",
        "base_impact": 0.92,
        "platforms": ["tiktok", "instagram"],
    },
    "skeptic_turned_believer": {
        "template": "I was [skeptical] about [product]... then I discovered [reveal]",
        "base_impact": 0.88,
        "platforms": ["tiktok", "instagram", "x"],
    },
    "stop_buying": {
        "template": "Stop buying [product] until you see [reveal]",
        "base_impact": 0.86,
        "platforms": ["tiktok", "x"],
    },
    "brutal_truth": {
        "template": "I tested [product] for [time]... here's the brutal truth",
        "base_impact": 0.84,
        "platforms": ["tiktok", "linkedin"],
    },
    "nobody_tells_you": {
        "template": "Nobody tells you this about [product]...",
        "base_impact": 0.80,
        "platforms": ["instagram", "tiktok"],
    },
    "data_surprise": {
        "template": "I analyzed [number] reviews of [product]... the results surprised me",
        "base_impact": 0.78,
        "platforms": ["linkedin", "x"],
    },
    "one_thing": {
        "template": "The one [feature] that completely [changed] my [experience]",
        "base_impact": 0.76,
        "platforms": ["instagram", "x"],
    },
    "worth_it": {
        "template": "Is [product] actually worth [price]? I [action] to find out",
        "base_impact": 0.74,
        "platforms": ["x", "linkedin"],
    },
    "market_winner": {
        "template": "The [category] market is [size]... here's who's actually winning",
        "base_impact": 0.70,
        "platforms": ["linkedin"],
    },
    "person_tried_it": {
        "template": "[Person] said I was [wasting] buying [product]... then they tried it",
        "base_impact": 0.72,
        "platforms": ["tiktok", "instagram"],
    },
}

# Default fill-ins when the payload does not provide real data.
_DEFAULT_PERSONS = ["friend", "partner", "brother", "dad", "colleague"]
_DEFAULT_CRITICISMS = ["a waste of money", "way overpriced", "completely overhyped"]
_DEFAULT_WASTING = ["crazy", "wasting money"]
_DEFAULT_SKEPTICISM = ["skeptical", "ready to return it", "doubtful"]
_DEFAULT_ACTIONS = ["ran the numbers", "put it to the test", "showed them the data"]
_DEFAULT_REVEALS = ["this one test", "what it actually does", "the numbers"]
_DEFAULT_CHANGES = ["changed", "transformed", "upgraded"]
_DEFAULT_EXPERIENCES = ["workflow", "setup", "morning routine"]
_DEFAULT_MARKET_SIZES = ["$80 billion", "$40 billion", "$25 billion"]

_PLATFORM_TONE = {
    "tiktok": {"emoji": "🔥", "max_len": 60, "suffix": "..."},
    "instagram": {"emoji": "✨", "max_len": 80, "suffix": "..."},
    "x": {"emoji": "🧵", "max_len": 100, "suffix": ""},
    "linkedin": {"emoji": "💡", "max_len": 120, "suffix": ""},
}

MAX_HISTORY = 500


class TitleEngine:
    """Deterministic, self-improving Oliver Henry title generator."""

    def __init__(self, history_path: str = "data/title_performance.json"):
        self.history_path = Path(history_path)
        # learned_weight[template][platform] = performance bonus (0-0.3)
        self._learned: Dict[str, Dict[str, float]] = {}
        self._load_learned()

    # -- public API -------------------------------------------------------

    def generate_titles(self, carousel: Dict[str, Any], platform: str = "tiktok",
                        count: int = 5) -> List[Dict[str, Any]]:
        """Generate up to `count` title variants ranked for the platform.

        Deterministic (same input -> same output, given the same history), so
        callers can safely persist the selected title and re-score later.
        """
        data = self._build_context(carousel)
        scored = []
        for tpl_id, tpl in TEMPLATES.items():
            try:
                title = self._fill(tpl["template"], data)
            except Exception as e:  # never let a single template kill the batch
                logger.debug(f"Title template {tpl_id} fill failed: {e}")
                continue
            if not title:
                continue
            impact = self._score(tpl_id, platform, tpl)
            scored.append({
                "title": title,
                "template": tpl_id,
                "platform": platform,
                "estimated_impact": round(impact, 3),
            })
        scored.sort(key=lambda v: v["estimated_impact"], reverse=True)
        scored = self._adapt_platform(scored[:count], platform)
        return scored

    def record_performance(self, platform: str, template: str,
                           metric: Optional[float] = None,
                           won: bool = False) -> None:
        """Feed a performance signal back into the learned weights.

        `won=True` (or a metric above 0.02, e.g. CTR) bumps the template's
        weight for that platform; a poor metric pulls it down. Never raises.
        """
        if template not in TEMPLATES:
            return
        strength = 0.02 if won else ((metric or 0.0) * 0.5)
        strength = max(-0.02, min(0.03, strength))
        bucket = self._learned.setdefault(template, {})
        bucket[platform] = max(0.0, min(0.3, bucket.get(platform, 0.0) + strength))
        self._prune()
        self._save_learned()

    def get_history_summary(self) -> Dict[str, Any]:
        """Current learned weights per template, for debugging/dashboards."""
        summary = {}
        for tpl_id, tpl in TEMPLATES.items():
            weights = self._learned.get(tpl_id, {})
            summary[tpl_id] = {
                "template": tpl["template"],
                "base_impact": tpl["base_impact"],
                "learned": weights,
            }
        return summary

    def select_best(self, carousel: Dict[str, Any], platform: str = "tiktok") -> Dict[str, Any]:
        """Return the single highest-impact variant (for a default title)."""
        variants = self.generate_titles(carousel, platform, count=1)
        if variants:
            return variants[0]
        return {"title": carousel.get("product_name", "The review"), "template": "fallback",
                "platform": platform, "estimated_impact": 0.0}

    # -- scoring ----------------------------------------------------------

    def _score(self, template_id: str, platform: str, tpl: Dict[str, Any]) -> float:
        base = float(tpl.get("base_impact", 0.5))
        suited = platform in tpl.get("platforms", [])
        if not suited:
            base *= 0.8
        learned = self._learned.get(template_id, {}).get(platform, 0.0)
        return min(1.0, base + learned)

    # -- template filling -------------------------------------------------

    def _build_context(self, carousel: Dict[str, Any]) -> Dict[str, str]:
        """Extract the fill-in values from the carousel payload."""
        carousel = carousel or {}
        verdict = carousel.get("verdict", {}) or {}
        breakdown = verdict.get("breakdown", {}) or {}
        product = str(carousel.get("product_name") or "this product")
        price = carousel.get("price") or ""
        category = str(carousel.get("category") or self._guess_category(product))

        # Best criterion becomes the "reveal" / the "one feature".
        best_criterion = ""
        if isinstance(breakdown, dict) and breakdown:
            try:
                best_criterion = max(breakdown, key=lambda k: float(breakdown[k] or 0))
            except (TypeError, ValueError):
                best_criterion = ""

        label = str(verdict.get("label") or "")
        overall = verdict.get("overall")
        try:
            score_float = float(overall or 0)
        except (TypeError, ValueError):
            score_float = 0.0

        # criticism is the doubt the person is proven wrong about: a low-scoring
        # product is "a waste of money", otherwise the skeptic doubts the hype.
        if score_float > 0 and score_float < 6.5:
            criticism = "a waste of money"
        else:
            criticism = "overhyped"

        return {
            "person": self._pick("persons"),
            "criticism": criticism,
            "wasting": self._pick("wasting"),
            "skeptical": self._pick("skepticism"),
            "action": self._pick("actions"),
            "reveal": best_criterion or self._pick("reveals"),
            "time": self._pick_time(),
            "number": self._pick_number(),
            "feature": best_criterion or "setting",
            "changed": self._pick("changes"),
            "experience": self._pick("experiences"),
            "price": self._price(price),
            "product": product,
            "category": category or "product",
            "size": self._pick("market_sizes"),
        }

    def _fill(self, template: str, data: Dict[str, str]) -> str:
        out = template
        for key, value in data.items():
            out = out.replace(f"[{key}]", value)
        if "[product]" in out:
            return ""
        return out

    # -- platform adaptation ----------------------------------------------

    def _adapt_platform(self, variants: List[Dict[str, Any]], platform: str) -> List[Dict[str, Any]]:
        tone = _PLATFORM_TONE.get(platform, _PLATFORM_TONE["tiktok"])
        max_len = tone["max_len"]
        for v in variants:
            title = v["title"]
            if len(title) > max_len:
                title = title[:max_len].rstrip(" .") + "..."
            if tone["emoji"] and platform != "linkedin":
                pass  # the hook is added by the platform skill engine later
            v["title"] = title
        return variants

    # -- helpers ----------------------------------------------------------

    def _price(self, price) -> str:
        price = str(price or "").strip()
        if price and any(ch.isdigit() for ch in price):
            return f"the {price}"
        return "the money"

    def _pick(self, key: str) -> str:
        options = {
            "persons": _DEFAULT_PERSONS,
            "criticisms": _DEFAULT_CRITICISMS,
            "wasting": _DEFAULT_WASTING,
            "skepticism": _DEFAULT_SKEPTICISM,
            "actions": _DEFAULT_ACTIONS,
            "reveals": _DEFAULT_REVEALS,
            "changes": _DEFAULT_CHANGES,
            "experiences": _DEFAULT_EXPERIENCES,
            "market_sizes": _DEFAULT_MARKET_SIZES,
        }
        opts = options.get(key, [])
        if not opts:
            return ""
        # deterministic rotation so identical payloads yield identical output
        idx = sum(ord(c) for c in "".join(opts)) % len(opts)
        return opts[idx]

    def _pick_time(self) -> str:
        return "30 days"

    def _pick_number(self) -> str:
        return "10,000"

    def _guess_category(self, product: str) -> str:
        for keyword, cat in [
            ("headphone", "headphones"),
            ("earbud", "earbuds"),
            ("speaker", "speakers"),
            ("watch", "smartwatch"),
            ("vacuum", "vacuum cleaners"),
            ("webcam", "webcams"),
            ("monitor", "monitors"),
            ("camera", "cameras"),
        ]:
            if keyword.lower() in str(product).lower():
                return cat
        return "product"

    # -- persistence ------------------------------------------------------

    def _load_learned(self) -> None:
        try:
            if self.history_path.exists():
                raw = json.loads(self.history_path.read_text(encoding="utf-8"))
                self._learned = {
                    t: {p: float(w) for p, w in (data.get("learned") or {}).items()}
                    for t, data in raw.items() if isinstance(data, dict)
                }
        except Exception as e:
            logger.warning(f"Could not load title performance history: {e}")
            self._learned = {}

    def _save_learned(self) -> None:
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                t: {"template": TEMPLATES[t]["template"], "learned": w}
                for t, w in self._learned.items()
            }
            self.history_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not save title performance history: {e}")

    def _prune(self) -> None:
        total = sum(len(w) for w in self._learned.values())
        if total <= MAX_HISTORY:
            return
        # keep the most recent platforms per template, drop extras
        for tpl_id, weights in self._learned.items():
            if len(weights) > 4:
                keep = list(sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:4])
                self._learned[tpl_id] = dict(keep)

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()


_title_engine: Optional[TitleEngine] = None


def get_title_engine() -> TitleEngine:
    """Singleton accessor."""
    global _title_engine
    if _title_engine is None:
        _title_engine = TitleEngine()
    return _title_engine
