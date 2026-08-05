"""platform_skill.py — Viral Content Engine per-platform adapter.

Adapts a 6-slide carousel payload into platform-optimized content for TikTok,
Instagram, X, and LinkedIn. Loads the per-platform rules from the markdown
skill files in abvorn/core/skills/ (for reading/reference), while the
mechanical adaptation (caption, hashtags, hook tone, visual style) lives in
plain dicts here so it works without parsing markdown.

Usage:
    from abvorn.core.platform_skill import get_platform_skill
    skill = get_platform_skill()
    out = skill.generate_platform_content(carousel, "tiktok")
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("abvorn.platform_skill")

PLATFORM_RULES: Dict[str, Dict[str, Any]] = {
    "tiktok": {
        "tone": "high_energy",
        "max_caption": 200,
        "max_hashtags": 5,
        "visual_style": "bright, high contrast, bold colors, text overlay",
        "platform_tags": ["#HonestReview", "#ProductReview"],
    },
    "instagram": {
        "tone": "aspirational",
        "max_caption": 2200,
        "max_hashtags": 30,
        "visual_style": "polished, aesthetic, clean, warm tones",
        "platform_tags": ["#ProductReview", "#BuyingGuide", "#TechReview"],
    },
    "x": {
        "tone": "sharp",
        "max_caption": 280,
        "max_hashtags": 3,
        "visual_style": "bold text, minimalist, high contrast",
        "platform_tags": ["#Review", "#BuyingGuide"],
    },
    "linkedin": {
        "tone": "professional",
        "max_caption": 3000,
        "max_hashtags": 5,
        "visual_style": "clean, professional, data visualization",
        "platform_tags": ["#ConsumerInsights", "#BuyingGuide"],
    },
}

HOOK_TONE_EMOJI = {
    "high_energy": "🔥",
    "aspirational": "✨",
    "sharp": "🧵",
    "professional": "💡",
}


class PlatformSkillEngine:
    """Generate platform-adapted content from a single carousel payload."""

    def __init__(self, skills_dir: str = "abvorn/core/skills",
                 history_path: str = "data/platform_performance_history.json"):
        self.skills_dir = Path(skills_dir)
        self.history_path = Path(history_path)
        self.platforms = ["tiktok", "instagram", "x", "linkedin"]
        self.performance_history: List[Dict] = self._load_history()

    # -- public API -------------------------------------------------------
    def load_skill_file(self, platform: str) -> str:
        f = self.skills_dir / f"{platform}_content.md"
        if f.exists():
            return f.read_text(encoding="utf-8")
        return ""

    def generate_platform_title(self, carousel: Dict[str, Any], platform: str) -> str:
        """Generate a scroll-stopping Oliver Henry title for the platform.

        Uses the Title Engine's variants (ranked by impact + learned history)
        and falls back to the existing hook when the engine is unavailable.
        """
        try:
            from abvorn.core.title_engine import get_title_engine
            best = get_title_engine().select_best(carousel, platform)
            if best.get("title"):
                return best["title"]
        except Exception as e:
            logger.warning(f"Title engine unavailable: {e}")
        hook = str(carousel.get("hook") or "")
        return hook if hook else str(carousel.get("product_name") or "The review")

    def generate_platform_content(self, carousel: Dict[str, Any], platform: str) -> Dict[str, Any]:
        config = PLATFORM_RULES.get(platform, {})
        hook = carousel.get("hook", "")
        verdict = carousel.get("verdict", {}) or {}
        score = verdict.get("overall", 0)
        product = carousel.get("product_name", "product")
        slides = carousel.get("slides", {}) or {}

        return {
            "platform": platform,
            "tone": config.get("tone"),
            "title": self.generate_platform_title(carousel, platform),
            "hook": self._adapt_hook(hook, config),
            "caption": self._adapt_caption(product, score, hook, config),
            "hashtags": self._adapt_hashtags(carousel.get("hashtags", []), config),
            "visual_style": config.get("visual_style", "clean"),
            "slides": slides,
            "skill_file": self.skill_ref(platform),
        }

    def update_from_performance(self, platform: str, data: Dict[str, Any]) -> None:
        self.performance_history.append({"platform": platform, "data": data})
        if len(self.performance_history) > 100:
            self.performance_history = self.performance_history[-100:]
        self._save_history()

    # -- persistence ------------------------------------------------------
    def _load_history(self) -> List[Dict]:
        try:
            if self.history_path.exists():
                return json.loads(self.history_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Could not load performance history: {e}")
        return []

    def _save_history(self) -> None:
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            self.history_path.write_text(
                json.dumps(self.performance_history, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not save performance history: {e}")

    def get_performance_history(self, platform: str = None) -> List[Dict]:
        if platform:
            return [h for h in self.performance_history if h.get("platform") == platform]
        return list(self.performance_history)

    # -- internal helpers -------------------------------------------------
    def _adapt_hook(self, hook: str, config: Dict) -> str:
        hook = str(hook or "").strip()
        if not hook:
            return hook
        emoji = HOOK_TONE_EMOJI.get(config.get("tone", ""), "")
        max_len = config.get("max_caption", 380)
        trimmed = hook[: max_len - 20]
        if config.get("tone") == "professional":
            return f"💡 {trimmed}..."
        return f"{trimmed} {emoji}".strip()

    def _adapt_caption(self, product: str, score, hook: str, config: Dict) -> str:
        tone = config.get("tone", "aspirational")
        templates = {
            "high_energy": f"🔥 {hook}... Full review → link in bio! #HonestReview",
            "aspirational": f"{hook}\n\n✨ Score: {score}/10\n🔗 Link in bio for the full review!\n\nWhich product next? 👇",
            "sharp": f"🧵 {hook}\n\nFull review: link in bio\n\nScore: {score}/10",
            "professional": f"💡 {hook}\n\n📊 Abvorn Score: {score}/10\n\n🔗 Read the full analysis: link in bio\n\nYour take on {product}? 👇",
        }
        cap = templates.get(tone, templates["aspirational"])
        max_len = config.get("max_caption", 3000)
        if len(cap) > max_len:
            cap = cap[: max_len - 3] + "..."
        return cap

    def _adapt_hashtags(self, hashtags: List[str], config: Dict) -> List[str]:
        tags = ["#Abvorn"] + list(config.get("platform_tags", [])) + list(hashtags or [])
        seen = []
        for t in tags:
            t = str(t).strip()
            if t and t not in seen:
                seen.append(t)
        return seen[: config.get("max_hashtags", 5)]

    def skill_ref(self, platform: str) -> str:
        return f"abvorn/core/skills/{platform}_content.md"


_platform_skill = None


def get_platform_skill() -> PlatformSkillEngine:
    global _platform_skill
    if _platform_skill is None:
        _platform_skill = PlatformSkillEngine()
    return _platform_skill