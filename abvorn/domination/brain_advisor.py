"""BrainAdvisor — industry-knowledge decision support for the business loop.

The brain (Obsidian/Notebook LM + Graphify index) doesn't write copy. It holds
industry knowledge, best practices, and cross-book patterns that should inform
*decisions*: which niche to double down on, when to pivot, what the growth
playbook says for a category.

This advisor is strictly advisory:
- It never blocks or fails a cycle (every entry point is try/except).
- If the brain is unavailable or returns nothing, the loop proceeds unchanged.
- Guidance is recorded into state meta so the digest/notifier can surface it
  to the operator, turning "decision" + "knowledge" into an auditable record.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger("abvorn.domination.brain_advisor")


class BrainAdvisor:
    """Queries the brain for growth/best-practice guidance on decisions."""

    def __init__(self, brain=None):
        self._brain = brain
        self._asked = set()  # cache per question (avoid hammering the brain)

    def _get_brain(self):
        if self._brain is None:
            try:
                from ..core.brain import get_brain
                self._brain = get_brain()
            except Exception as e:
                logger.warning(f"Brain unavailable (non-fatal): {e}")
        return self._brain

    def guidance(self, question: str, limit: int = 3) -> list:
        """Best-practice insights for a decision question. Empty on any failure."""
        qkey = f"{question}|{limit}"
        if qkey in self._asked:
            return []
        self._asked.add(qkey)
        brain = self._get_brain()
        if brain is None:
            return []
        try:
            return brain.query(question, limit=limit)
        except Exception as e:
            logger.warning(f"Brain guidance query failed (non-fatal): {e}")
            return []

    # ── decision-specific queries ─────────────────────────────────────────

    def growth_guidance(self, niche: str) -> list:
        """What the industry knowledge base says about growing this niche."""
        lines = [
            f"What do industry best practices say about growing a {niche} review/comparison site?",
            "What strategies are proven for niche review sites to grow?",
            f"How should we prioritize investment in the {niche} category?",
        ]
        for q in lines:
            out = self.guidance(q, limit=2)
            if out:
                return out
        return []

    def pivot_guidance(self, niche: str) -> list:
        """Knowledge-base check before abandoning a niche."""
        lines = [
            f"What does industry knowledge say before deciding to stop investing in the {niche} category?",
            f"When should a {niche} review site pivot or change angle?",
        ]
        for q in lines:
            out = self.guidance(q, limit=2)
            if out:
                return out
        return []


def snapshot_guidance(advisor: BrainAdvisor, analytics: dict) -> dict:
    """Build {slug: {decision, insights}} guidance for the niches that moved.

    Only niches with a measurable GA4 score get guidance; the rest are skipped
    so the brain is only consulted for real decisions.
    """
    snapshot = {}
    for slug, data in analytics.items():
        views = data.get("views", 0)
        score = views + data.get("users", 0) * 2
        if views <= 0:
            continue
        if score >= 100:
            decision = "double_down"
            insights = advisor.growth_guidance(slug)
        elif score < 10:
            decision = "pivot"
            insights = advisor.pivot_guidance(slug)
        else:
            continue
        snapshot[slug] = {
            "decision": decision,
            "score": round(score, 1),
            "insights": [
                {"source": r.get("source", "Brain"), "insight": r.get("insight", "")[:300]}
                for r in insights[:2]
                if r.get("insight")
            ],
        }
    return snapshot


def run_brain_advisory(advisor: BrainAdvisor, analytics: dict,
                       state) -> dict:
    """Non-fatal entry point for the daemon: consult the brain on decisions,
    persist the guidance into state meta, and return what was stored.

    Only decisions backed by actual knowledge-base insights are persisted —
    a broken or empty brain must not cause noise in the digest.
    """
    try:
        snapshot = snapshot_guidance(advisor, analytics or {})
        kept = {
            slug: info for slug, info in snapshot.items()
            if info.get("insights")
        }
        if kept:
            state.set_meta("brain_advisory", json.dumps(kept))
        return kept
    except Exception as e:
        logger.warning(f"Brain advisory failed (non-fatal): {e}")
        return {}