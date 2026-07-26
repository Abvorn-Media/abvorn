"""HookTester — tests hook variants and tracks performance."""

import logging
from typing import Optional
from collections import defaultdict

logger = logging.getLogger("abvorn.hooks.tester")

class HookTester:
    """Tracks hook performance across posts, platforms, and niches."""

    def __init__(self, state=None):
        self.state = state

    def record_hook_use(self, post_id: int, hook_type: str, hook_text: str,
                         platform: str = "blog", niche: str = ""):
        """Record that a hook variant was used."""
        if not self.state:
            return
        self.state.set_meta(f"hook:{post_id}:{platform}", {
            "hook_type": hook_type,
            "hook_text": hook_text,
            "platform": platform,
            "niche": niche,
            "used_at": __import__("datetime").datetime.now().isoformat()
        })

    def record_hook_performance(self, post_id: int, platform: str,
                                  engagement_score: float):
        """Record how a hook performed based on engagement."""
        if not self.state:
            return
        key = f"hook:{post_id}:{platform}"
        data = self.state.get_meta(key)
        if not data:
            return
        hook_type = data.get("hook_type", "unknown")
        self.state.set_meta(f"hook_perf:{hook_type}:{platform}:{post_id}", {
            "hook_type": hook_type,
            "platform": platform,
            "engagement": engagement_score,
            "recorded_at": __import__("datetime").datetime.now().isoformat()
        })

    def get_best_hooks(self, niche: str = None, platform: str = None, limit: int = 5) -> list:
        """Get top-performing hook types."""
        if not self.state:
            return []
        all_meta = self.state.get_all_intel_patterns() if hasattr(self.state, 'get_all_intel_patterns') else []
        # Query hook performance from meta
        hook_perfs = defaultdict(lambda: {"count": 0, "total_engagement": 0})
        try:
            # Use a pattern-based query approach
            raw = self.state.get_meta("hook_perf:all", {}).get("hooks", [])
            for h in raw:
                if niche and h.get("niche") != niche:
                    continue
                if platform and h.get("platform") != platform:
                    continue
                key = h["hook_type"]
                hook_perfs[key]["count"] += 1
                hook_perfs[key]["total_engagement"] += h.get("engagement", 0)
        except Exception:
            return []

        results = []
        for hook_type, data in hook_perfs.items():
            results.append({
                "hook_type": hook_type,
                "avg_engagement": round(data["total_engagement"] / max(data["count"], 1), 2),
                "uses": data["count"]
            })
        return sorted(results, key=lambda x: -x["avg_engagement"])[:limit]

    def analyze_hooks(self, niche: str = None) -> str:
        """Hook performance report."""
        best = self.get_best_hooks(niche, limit=5)
        lines = ["=" * 60, "HOOK PERFORMANCE REPORT", "=" * 60]
        if best:
            lines.append("\nTop Hook Types by Engagement:")
            for h in best:
                lines.append(f"  {h['hook_type']}: {h['avg_engagement']} avg engagement ({h['uses']} uses)")
        else:
            lines.append("\nNo hook data yet. Start tracking to see what works.")
        return "\n".join(lines)