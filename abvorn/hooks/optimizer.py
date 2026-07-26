"""HookOptimizer — picks the best hook for each context based on data."""

import logging
from typing import Optional

logger = logging.getLogger("abvorn.hooks.optimizer")

class HookOptimizer:
    """Selects the optimal hook variant for a given context."""

    def __init__(self, generator=None, tester=None):
        self.generator = generator
        self.tester = tester

    def pick_best_hook(self, niche: str, product: str = "", angle: str = "",
                        platform: str = "blog") -> dict:
        """Pick the best hook for a given context based on historical data."""
        best_type = None
        if self.tester:
            best_hooks = self.tester.get_best_hooks(niche, platform, limit=3)
            if best_hooks:
                best_type = best_hooks[0]["hook_type"]

        if not self.generator:
            return {"type": "direct", "hook": f"Best {niche} of 2026", "platforms": ["blog"]}

        variants = self.generator.generate_variants(niche, product, angle, 8)

        if best_type:
            matched = [v for v in variants if v["type"] == best_type]
            if matched:
                return matched[0]

        return variants[0]

    def optimize_hook_text(self, hook: str, platform: str) -> str:
        """Ensure hook fits platform constraints."""
        limits = {"x": 100, "tiktok": 100, "instagram": 120, "linkedin": 200, "blog": 300}
        max_len = limits.get(platform, 200)
        if len(hook) > max_len:
            hook = hook[:max_len - 3] + "..."
        if platform in ("x", "tiktok") and not hook.endswith(("?", "!", ".", "🧵", "👇")):
            hook += " 👇"
        return hook

    def hool(self, niche: str, product: str = "", angle: str = "",
                        platform: str = "blog") -> str:
        """One-call method to get the optimal hook."""
        best = self.pick_best_hook(niche, product, angle, platform)
        return self.optimize_hook_text(best["hook"], platform)