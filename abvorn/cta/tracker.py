"""CTATracker — records CTA events and feeds into the intelligence engine."""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("abvorn.cta.tracker")

CTA_TYPES = ["affiliate_link", "button", "sticky_bar", "email_link", "social_cta", "inline_link", "hero_cta"]
CTA_LOCATIONS = ["header", "sidebar", "inline", "sticky", "footer", "comparison", "within_review", "after_content", "email"]

class CTATracker:
    """Tracks CTA impressions, clicks, and conversions."""

    def __init__(self, state=None, intel_engine=None):
        self.state = state
        self.intel = intel_engine

    def track_impression(self, post_id: int, cta_id: str, cta_type: str = "affiliate_link",
                          cta_text: str = "", cta_location: str = "inline",
                          niche: str = "", platform: str = "", visitor_hash: str = ""):
        if not self.state:
            logger.warning("No state — CTA impression not tracked")
            return
        self.state.log_cta_event(
            post_id=post_id, cta_id=cta_id, cta_type=cta_type,
            event_type="impression", cta_text=cta_text,
            cta_location=cta_location, visitor_hash=visitor_hash,
            niche=niche, platform=platform
        )

    def track_click(self, post_id: int, cta_id: str, cta_type: str = "affiliate_link",
                     cta_text: str = "", cta_location: str = "inline",
                     niche: str = "", platform: str = ""):
        if not self.state:
            logger.warning("No state — CTA click not tracked")
            return
        self.state.log_cta_event(
            post_id=post_id, cta_id=cta_id, cta_type=cta_type,
            event_type="click", cta_text=cta_text,
            cta_location=cta_location, niche=niche, platform=platform
        )
        if self.intel:
            try:
                self.intel.ingest_cycle(
                    {"niche": niche, "selected_angle": cta_text, "article_html": ""},
                    {"decision_trigger": cta_type, "niche": niche},
                    outcome_success=True
                )
            except Exception as e:
                logger.warning(f"Failed to feed click to intel: {e}")

    def track_conversion(self, post_id: int, cta_id: str, niche: str = ""):
        if not self.state:
            return
        self.state.log_cta_event(
            post_id=post_id, cta_id=cta_id, cta_type="affiliate_link",
            event_type="conversion", niche=niche
        )

    def get_stats(self, post_id: int = None, niche: str = None) -> dict:
        if not self.state:
            return {"total_ctas": 0}
        return self.state.get_cta_summary(niche=niche)

    def generate_cta_id(self, post_id: int, cta_type: str, location: str, index: int = 0) -> str:
        return f"cta_{post_id}_{cta_type}_{location}_{index}"

    def generate_cta_html(self, post_id: int, cta_type: str, cta_text: str,
                           cta_url: str, cta_location: str = "inline",
                           niche: str = "", index: int = 0) -> str:
        cta_id = self.generate_cta_id(post_id, cta_type, cta_location, index)
        # Track impression via JS
        onclick = f"ctaClick('{cta_id}',{post_id},'{cta_type}','{cta_text}','{cta_location}','{niche}')"
        return (f'<a href="{cta_url}" class="cta-link" data-cta-id="{cta_id}" '
                f'onclick="{onclick};return true" rel="nofollow sponsored" target="_blank">'
                f'{cta_text} &rarr;</a>')