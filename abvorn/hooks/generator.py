"""HookGenerator — generates hook variants for headlines, social, email."""

import logging
from typing import Optional

logger = logging.getLogger("abvorn.hooks.generator")

HOOK_PATTERNS = {
    "problem": "Stop [pain_point] — Here's How [solution] Actually Works",
    "curiosity": "The #1 [product_type] [expert] Don't Want You to Know About",
    "social_proof": "After Testing [number] [product_type], Here's the Only One Worth Buying",
    "direct": "The Best [product_type] for [specific_need] in [year]",
    "comparison": "[Product_A] vs [Product_B]: Which [product_type] Really Wins?",
    "question": "Looking for the Perfect [product_type]? Start Here",
    "fear": "Don't Buy Another [product_type] Until You Read This",
    "benefit": "[number] Ways a Better [product_type] Will Change Your [life_area]",
}

class HookGenerator:
    """Generates hook variants for different platforms and contexts."""

    def __init__(self, router=None):
        self.router = router

    def generate_variants(self, niche: str, product: str = "", angle: str = "",
                           count: int = 5) -> list:
        """Generate hook variants for blog headlines."""
        patterns = list(HOOK_PATTERNS.keys())
        if angle:
            if "problem" in angle.lower():
                patterns = ["problem", "fear", "question", "direct", "curiosity"]
            elif "comparison" in angle.lower():
                patterns = ["comparison", "direct", "social_proof", "benefit", "question"]
            elif "best" in angle.lower():
                patterns = ["social_proof", "direct", "curiosity", "benefit", "question"]

        variants = []
        for i, ptype in enumerate(patterns[:count]):
            template = HOOK_PATTERNS[ptype]
            hook = template
            if niche:
                hook = hook.replace("[product_type]", niche)
            if product:
                hook = hook.replace("[Product_A]", product)
            year = "2026"
            hook = hook.replace("[year]", year)
            hook = hook.replace("[number]", str(3 + i * 2))
            hook = hook.replace("[expert]", "Experts" if i % 2 == 0 else "Insiders")
            hook = hook.replace("[specific_need]", "Everyday Use" if i % 2 == 0 else "Professional Results")
            hook = hook.replace("[pain_point]", "Wasting Money on Bad Products")
            hook = hook.replace("[solution]", "Research-Backed Selection")
            hook = hook.replace("[life_area]", "Daily Routine")

            variants.append({
                "type": ptype,
                "hook": hook,
                "platforms": self._platforms_for_type(ptype)
            })
        return variants

    def generate_social_hook(self, niche: str, product: str = "", platform: str = "x") -> str:
        """Generate a platform-specific social hook."""
        if platform in ("x", "tiktok"):
            return f"Stop buying the wrong {niche}. Here's what actually works. 🧵"
        elif platform == "linkedin":
            return f"After extensive research on {niche}, here's what I found most professionals get wrong:"
        elif platform == "instagram":
            return f"The {niche} secret no one talks about 👀"
        elif platform == "pinterest":
            return f"The Ultimate Guide to Finding the Perfect {niche}"
        elif platform == "facebook":
            return f"If you're looking for a {niche}, read this before you buy anything."
        elif platform == "youtube":
            return f"I Tested 10 {niche} — Here's the One That Won"
        return f"Check out the best {niche} of {2026}"

    def generate_email_subject(self, niche: str, persona_name: str = "") -> list:
        """Generate email subject line variants."""
        name_tag = f"{persona_name}, " if persona_name else ""
        return [
            f"{name_tag}The {niche} Guide We Promised You",
            f"{name_tag}Stop Searching — We Found the Best {niche}",
            f"{name_tag}Your Perfect {niche} Awaits (We Tested Them All)",
            f"{name_tag}Don't Buy a {niche} Until You Read This",
            f"{name_tag}Finally: A {niche} That Actually Delivers",
        ]

    def _platforms_for_type(self, hook_type: str) -> list:
        mapping = {
            "problem": ["x", "facebook", "email"],
            "curiosity": ["x", "tiktok", "instagram", "facebook"],
            "social_proof": ["linkedin", "blog", "pinterest"],
            "direct": ["blog", "google", "pinterest"],
            "comparison": ["blog", "youtube", "pinterest"],
            "question": ["x", "facebook", "email"],
            "fear": ["x", "facebook", "email"],
            "benefit": ["linkedin", "blog", "email"],
        }
        return mapping.get(hook_type, ["blog"])