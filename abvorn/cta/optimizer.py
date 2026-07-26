"""CTAOptimizer — suggests CTA improvements based on performance data + brain CRO principles."""

import logging
from typing import Optional
from abvorn.brain.principles import CRO_PRINCIPLES

logger = logging.getLogger("abvorn.cta.optimizer")

BEST_PRACTICES = {
    "affiliate_link": ["check price on Amazon", "see price on Amazon", "read reviews on Amazon", "view on Amazon"],
    "button": ["Buy Now", "Shop Now", "Get Yours Today", "See the Deal"],
    "sticky_bar": ["Best Price →", "Shop Now →", "Check Price →"],
    "inline_link": ["learn more here", "check the latest price", "see current deals"],
}

CTAs_TO_AVOID = [
    "click here", "this link", "go here", "more info",
]

class CTAOptimizer:
    """Analyzes CTA data and suggests improvements using CRO principles."""

    def __init__(self, state=None):
        self.state = state

    def get_cta_suggestions(self, niche: str = None) -> list:
        """Get CTA improvement suggestions based on data + CRO principles."""
        suggestions = []
        stats = self.state.get_cta_stats(niche=niche) if self.state else []

        low_performers = [s for s in stats if s["impressions"] > 10 and s["click_rate"] < 0.02]
        for cta in low_performers[:3]:
            principle_hint = ""
            if cta["cta_type"] == "affiliate_link" and "price" not in (cta["cta_text"] or "").lower():
                principle_hint = f" CRO principle: specificity — 'See price on Amazon' beats vague text."
            suggestions.append({
                "type": "low_performance",
                "cta_id": cta["cta_id"],
                "text": cta["cta_text"],
                "current_rate": cta["click_rate"],
                "principle": principle_hint,
                "suggestion": f"Replace '{cta['cta_text']}' with a stronger CTA. "
                              f"Try: '{BEST_PRACTICES.get(cta['cta_type'], ['shop now'])[0]}'"
                              f"{principle_hint}"
            })

        for s in stats:
            if s["cta_text"] and any(bad in s["cta_text"].lower() for bad in CTAs_TO_AVOID):
                suggestions.append({
                    "type": "weak_wording",
                    "cta_id": s["cta_id"],
                    "text": s["cta_text"],
                    "principle": f"CRO principle: specificity — vague CTAs kill conversion. Be exact.",
                    "suggestion": f"'{s['cta_text']}' violates specificity principle. Use action-oriented text like 'Check Price on Amazon'."
                })

        if self.state and niche:
            all_stats = self.state.get_cta_stats()
            niche_stats = [s for s in all_stats if s["niche"] == niche]
            if niche_stats:
                best_type = max(set(s["cta_type"] for s in niche_stats),
                               key=lambda t: sum(s["clicks"] for s in niche_stats if s["cta_type"] == t))
                suggestions.append({
                    "type": "best_type",
                    "niche": niche,
                    "best_cta_type": best_type,
                    "principle": f"CRO principle: defaults — lean into what's already working.",
                    "suggestion": f"'{best_type}' performs best in '{niche}' niche. Double down on this type."
                })

        # Add principle-based suggestions even without data
        suggestions.append({
            "type": "principle",
            "principle": f"CRO principle: reduction — check that every CTA has one clear action. No dual-purpose buttons.",
            "suggestion": "Audit each CTA: one link = one action. Never make 'click to learn more and maybe buy'."
        })

        return suggestions

    def optimize_cta_text(self, cta_text: str, cta_type: str) -> str:
        text_lower = cta_text.lower()
        for bad in CTAs_TO_AVOID:
            if bad in text_lower:
                alternatives = BEST_PRACTICES.get(cta_type, ["Shop Now"])
                return alternatives[0]
        return cta_text

    def get_optimization_report(self, niche: str = None) -> str:
        suggestions = self.get_cta_suggestions(niche)
        lines = ["=" * 60, "CTA OPTIMIZATION REPORT", "=" * 60]
        if not suggestions:
            lines.append("\nAll CTAs performing well. Continue monitoring.")
        for s in suggestions:
            lines.append(f"\n[{s['type'].upper()}]")
            principle = s.get("principle", "")
            if principle:
                lines.append(f"  {principle}")
            lines.append(f"  {s['suggestion']}")
        lines.append("")
        return "\n".join(lines)