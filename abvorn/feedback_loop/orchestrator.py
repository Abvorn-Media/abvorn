"""FeedbackOrchestrator — runs the full closed-loop cycle end-to-end."""

import logging
from datetime import datetime

logger = logging.getLogger("abvorn.feedback_loop.orchestrator")


class FeedbackOrchestrator:
    """Orchestrates the closed-loop feedback cycle.

    Flow:
      1. Collect user interactions via GA4 or local event store
      2. Feed engagement data into the FeedbackLearner
      3. Apply updated weights back to the Verdict Engine
      4. Trigger retraining if thresholds are met
    """

    def __init__(self, collector=None, learner=None, verdict_engine=None, state=None, min_interactions=100):
        self.collector = collector
        self.learner = learner
        self.verdict_engine = verdict_engine
        self.state = state
        self.min_interactions = min_interactions
        self.last_run = None

    def process_feedback(self, days: int = 7, niche_slug: str = None) -> dict:
        """Run one full feedback cycle. Returns a summary dict."""
        if not self.collector or not self.learner:
            return {"status": "skipped", "reason": "collector or learner not configured"}

        interactions = self.collector.get_recent_interactions(days=days)
        if len(interactions) < self.min_interactions:
            return {"status": "skipped", "reason": f"only {len(interactions)} interactions (need {self.min_interactions})"}

        by_product = self.collector.get_interactions_by_product(days=days)
        updated_categories = set()
        products_processed = 0

        for product_id, agg in by_product.items():
            if niche_slug and not product_id.startswith(niche_slug):
                continue
            verdict = self._get_product_verdict(product_id)
            if verdict:
                self.learner.update_from_engagement(niche_slug or "generic", product_id, verdict, agg)
                products_processed += 1

        overrides = self.learner.overrides
        if overrides:
            for ns, cats in overrides.items():
                for ck in cats:
                    updated_categories.add(f"{ns}.{ck}")

        needs_retrain = len(interactions) > self.min_interactions * 2
        if needs_retrain:
            self.learner.retrain_models()

        self.last_run = datetime.now().isoformat()

        return {
            "status": "ok",
            "interactions_processed": len(interactions),
            "products_updated": products_processed,
            "categories_adjusted": len(updated_categories),
            "retrained": needs_retrain,
            "updated_categories": sorted(updated_categories),
            "timestamp": self.last_run,
        }

    def _get_product_verdict(self, product_id: str) -> dict | None:
        """Retrieve a product's stored verdict."""
        if not self.state:
            return None
        try:
            verdict = self.state.get_verdict(product_id)
            return verdict
        except Exception:
            return None

    def get_status(self) -> dict:
        """Return current loop status."""
        return {
            "last_run": self.last_run,
            "min_interactions": self.min_interactions,
            "learner_overrides": dict(self.learner.overrides) if self.learner else {},
            "has_collector": self.collector is not None,
        }
