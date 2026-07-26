import logging
from .patterns import PersuasionPatternDB

logger = logging.getLogger("abvorn.intel.report")

class IntelReport:
    """Renders intelligence reports."""

    def generate_full_report(self, engine) -> str:
        """Generate full intelligence report."""
        stats = engine.pattern_db.get_stats() if hasattr(engine, 'pattern_db') else {}
        velocity = engine.get_learning_velocity() if hasattr(engine, 'get_learning_velocity') else {}

        lines = [
            "=" * 60,
            "CROSS-NICHE INTELLIGENCE REPORT",
            "=" * 60,
            "",
            f"Total Patterns: {stats.get('total', 0)}",
            f"Total Cycles: {velocity.get('total_cycles', 0)}",
            f"Learning Velocity: {velocity.get('patterns_per_cycle', 0)} patterns/cycle",
            f"Average Confidence: {stats.get('avg_confidence', 0)}",
            "",
            "Patterns by Type:",
        ]

        for ptype, count in stats.get("by_type", {}).items():
            lines.append(f"  {ptype}: {count}")

        lines.append("")
        lines.append("Top Niches by Pattern Count:")
        for n in stats.get("top_niches", []):
            lines.append(f"  {n['niche']}: {n['count']} patterns")

        if hasattr(engine, 'pattern_db'):
            high_conf = engine.pattern_db.get_high_confidence(0.8)
            if high_conf:
                lines.append("")
                lines.append("Top High-Confidence Patterns (>= 0.8):")
                for p in high_conf[:5]:
                    lines.append(f"  [{p['pattern_type']}] {p['content']} ({p['confidence']})")

        if stats.get("top_niches", []):
            transferable = []
            if hasattr(engine, 'pattern_db'):
                for n in stats.get("top_niches", []):
                    t = engine.pattern_db.get_transferable(n["niche"], "any", 2)
                    transferable.extend(t)
            if transferable:
                lines.append("")
                lines.append("Most Transferable Patterns:")
                for p in transferable[:3]:
                    lines.append(f"  {p['content']} (from: {p.get('source_niche', 'unknown')})")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)