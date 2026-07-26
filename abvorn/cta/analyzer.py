"""CTAAnalyzer — analyzes CTA performance across dimensions."""

import logging
from typing import Optional
from collections import defaultdict

logger = logging.getLogger("abvorn.cta.analyzer")

class CTAAnalyzer:
    """Analyzes CTA performance — by type, location, niche, text."""

    def __init__(self, state=None):
        self.state = state

    def analyze_by_type(self, niche: str = None) -> list:
        """Best performing CTA types (button vs link vs sticky)."""
        stats = self.state.get_cta_stats(niche=niche) if self.state else []
        by_type = defaultdict(lambda: {"impressions": 0, "clicks": 0, "conversions": 0, "count": 0})
        for s in stats:
            t = s["cta_type"]
            by_type[t]["impressions"] += s["impressions"]
            by_type[t]["clicks"] += s["clicks"]
            by_type[t]["conversions"] += s["conversions"]
            by_type[t]["count"] += 1
        results = []
        for cta_type, data in by_type.items():
            results.append({
                "cta_type": cta_type,
                "impressions": data["impressions"],
                "clicks": data["clicks"],
                "conversions": data["conversions"],
                "click_rate": round(data["clicks"] / max(data["impressions"], 1), 3),
                "conversion_rate": round(data["conversions"] / max(data["clicks"], 1), 3),
                "count": data["count"]
            })
        return sorted(results, key=lambda x: -x["click_rate"])

    def analyze_by_location(self, niche: str = None) -> list:
        """Best performing CTA locations (inline vs sticky vs footer)."""
        stats = self.state.get_cta_stats(niche=niche) if self.state else []
        by_loc = defaultdict(lambda: {"impressions": 0, "clicks": 0, "count": 0})
        for s in stats:
            loc = s["cta_location"]
            by_loc[loc]["impressions"] += s["impressions"]
            by_loc[loc]["clicks"] += s["clicks"]
            by_loc[loc]["count"] += 1
        results = []
        for location, data in by_loc.items():
            results.append({
                "location": location,
                "impressions": data["impressions"],
                "clicks": data["clicks"],
                "click_rate": round(data["clicks"] / max(data["impressions"], 1), 3),
                "count": data["count"]
            })
        return sorted(results, key=lambda x: -x["click_rate"])

    def analyze_by_text(self, niche: str = None, limit: int = 10) -> list:
        """Best performing CTA text variants."""
        stats = self.state.get_cta_stats(niche=niche) if self.state else []
        by_text = defaultdict(lambda: {"impressions": 0, "clicks": 0, "count": 0})
        for s in stats:
            txt = s["cta_text"][:60] if s["cta_text"] else "(empty)"
            by_text[txt]["impressions"] += s["impressions"]
            by_text[txt]["clicks"] += s["clicks"]
            by_text[txt]["count"] += 1
        results = []
        for text, data in by_text.items():
            results.append({
                "text": text,
                "impressions": data["impressions"],
                "clicks": data["clicks"],
                "click_rate": round(data["clicks"] / max(data["impressions"], 1), 3),
                "count": data["count"]
            })
        return sorted(results, key=lambda x: -x["click_rate"])[:limit]

    def analyze_by_niche(self) -> list:
        """Which niches have the best CTA performance."""
        stats = self.state.get_cta_stats() if self.state else []
        by_niche = defaultdict(lambda: {"impressions": 0, "clicks": 0, "conversions": 0})
        for s in stats:
            n = s["niche"] or "unknown"
            by_niche[n]["impressions"] += s["impressions"]
            by_niche[n]["clicks"] += s["clicks"]
            by_niche[n]["conversions"] += s["conversions"]
        results = []
        for niche, data in by_niche.items():
            results.append({
                "niche": niche,
                "impressions": data["impressions"],
                "clicks": data["clicks"],
                "conversions": data["conversions"],
                "click_rate": round(data["clicks"] / max(data["impressions"], 1), 3)
            })
        return sorted(results, key=lambda x: -x["click_rate"])

    def full_report(self, niche: str = None) -> str:
        """Full CTA performance report as formatted string."""
        lines = ["=" * 60, "CTA PERFORMANCE REPORT", "=" * 60]
        by_type = self.analyze_by_type(niche)
        if by_type:
            lines.append("\nBy Type:")
            for t in by_type:
                lines.append(f"  {t['cta_type']}: {t['click_rate']*100:.1f}% CTR ({t['clicks']}/{t['impressions']})")
        by_loc = self.analyze_by_location(niche)
        if by_loc:
            lines.append("\nBy Location:")
            for l in by_loc:
                lines.append(f"  {l['location']}: {l['click_rate']*100:.1f}% CTR ({l['clicks']}/{l['impressions']})")
        by_text = self.analyze_by_text(niche, 5)
        if by_text:
            lines.append("\nTop CTAs by Text:")
            for t in by_text:
                lines.append(f"  \"{t['text']}\": {t['click_rate']*100:.1f}%")
        lines.append("")
        return "\n".join(lines)