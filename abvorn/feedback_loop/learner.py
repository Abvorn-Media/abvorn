"""FeedbackLearner — updates Verdict Engine weights based on real user engagement."""

import logging
from copy import deepcopy

logger = logging.getLogger("abvorn.feedback_loop.learner")


class FeedbackLearner:
    """Learns from user interactions to adjust Verdict Engine scoring weights.

    Higher engagement/conversion on products scored highly in a category
    reinforces that category's weight. Low engagement despite a high score
    suggests the weight should be reduced.
    """

    def __init__(self, verdict_engine=None, overrides: dict = None):
        self.verdict_engine = verdict_engine
        self._overrides = deepcopy(overrides) if overrides else {}

    @property
    def overrides(self) -> dict:
        return self._overrides

    def update_from_engagement(self, niche_slug: str, product_id: str, product_verdict: dict, interactions: dict):
        """Update weights based on aggregate interactions for a product.

        interactions dict: {page_views, affiliate_clicks, conversions, revenue}
        """
        if not product_verdict or "breakdown" not in product_verdict:
            return

        breakdown = product_verdict.get("breakdown", {})
        clicks = interactions.get("affiliate_clicks", 0)
        conversions = interactions.get("conversions", 0)
        views = interactions.get("page_views", 1)

        if views < 5:
            return

        click_rate = clicks / views
        conv_rate = conversions / views if views > 0 else 0

        for cat_label, score in breakdown.items():
            if not isinstance(score, (int, float)) or score == 0:
                continue

            expected = score / 10.0
            actual = click_rate + conv_rate
            gap = expected - actual

            if gap > 0.2:
                adjustment = -0.02
            elif gap < -0.1:
                adjustment = 0.01
            else:
                continue

            cat_key = self._label_to_key(cat_label, niche_slug)
            if cat_key:
                current = self._overrides.get(niche_slug, {}).get(cat_key, 0.0)
                new_weight = max(0.05, min(0.50, current + adjustment))
                if self.verdict_engine:
                    self._overrides = self.verdict_engine.apply_learner_weight_update(
                        self._overrides, niche_slug, cat_key, new_weight
                    )

    def update_from_regret(self, niche_slug: str, product_id: str, product_verdict: dict, regret_data: dict):
        """Score down categories where users express regret."""
        for cat_label, regret_score in regret_data.items():
            if regret_score < 0.3:
                continue
            cat_key = self._label_to_key(cat_label, niche_slug)
            if cat_key:
                current = self._overrides.get(niche_slug, {}).get(cat_key, 0.0)
                new_weight = max(0.05, min(0.50, current - 0.015))
                if self.verdict_engine:
                    self._overrides = self.verdict_engine.apply_learner_weight_update(
                        self._overrides, niche_slug, cat_key, new_weight
                    )

    def retrain_models(self):
        """Trigger full weight recalculation if enough data has accumulated.

        Currently a no-op placeholder for future ML-based retraining.
        """
        logger.info("FeedbackLearner.retrain_models() called — ready for ML integration")
        return self._overrides

    @staticmethod
    def _label_to_key(cat_label: str, niche_slug: str) -> str | None:
        """Map a breakdown label back to weight key.

        Tries exact match first, then fuzzy against CATEGORY_WEIGHTS.
        """
        from abvorn.core.verdict import CATEGORY_WEIGHTS
        weights = CATEGORY_WEIGHTS.get(niche_slug) or {}
        for key, cfg in weights.items():
            if cfg.get("label", "").lower() == cat_label.lower():
                return key
        return None
