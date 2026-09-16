"""Opportunity discovery — finds untapped affiliate niches."""

import logging, re
from datetime import datetime


logger = logging.getLogger("abvorn.discovery")

# Maps trend-scanner subcategories onto the site's category taxonomy. An
# opportunity must land under a real site category (creating it if missing)
# so every shared page fits the navigation and category model.
SITE_CATEGORY_MAP = {
    "tv": "tv",
    "television": "tv",
    "televisions": "tv",
    "4k tv": "tv",
    "4k tvs": "tv",
    "monitor": "4k-monitors",
    "monitors": "4k-monitors",
    "laptop": "laptops",
    "laptops": "laptops",
    "smart home": "smart-home",
    "smart-home": "smart-home",
    "smart home devices": "smart-home",
    "echo": "smart-home",
    "robot vacuum": "robot-vacuums",
    "robot vacuums": "robot-vacuums",
    "keyboard": "mechanical-keyboards",
    "keyboards": "mechanical-keyboards",
    "mouse": "gaming-mice",
    "mice": "gaming-mice",
    "gaming mouse": "gaming-mice",
    "headphones": "wireless-headphones",
    "earbuds": "wireless-earbuds",
    "webcam": "webcams",
    "webcams": "webcams",
    "fitness tracker": "fitness-trackers",
    "fitness trackers": "fitness-trackers",
    "smart watch": "fitness-trackers",
    "streaming": "streaming-devices",
    "streaming device": "streaming-devices",
}


def make_slug(name: str, max_len: int = 60) -> str:
    """Slugify without mid-word truncation or dangling hyphens."""
    if not name:
        return ""
    parts = [p for p in re.split(r"[^a-z0-9]+", name.lower()) if p]
    slug = "-".join(parts)
    if len(slug) > max_len:
        trunc = slug[:max_len]
        if trunc.endswith("-"):
            slug = trunc.rstrip("-")  # cut landed on a word boundary
        else:
            cut = trunc.rfind("-")  # mid-word cut: drop the partial fragment
            slug = trunc[:cut] if cut > 0 else trunc
    return slug.strip("-")


def resolve_site_category(opportunity: dict) -> str:
    """Resolve an opportunity to its site category.

    Prefers the discovery category stored on the opportunity; falls back to
    keyword inference from product/niche so legacy rows land somewhere sane
    instead of becoming orphan product pages.
    """
    cat = (opportunity.get("category") or "").strip().lower()
    if cat:
        return SITE_CATEGORY_MAP.get(cat, make_slug(cat) or "general")
    source = " ".join(filter(None, [
        opportunity.get("product_name"), opportunity.get("niche"),
    ])).lower()
    for key, slug in SITE_CATEGORY_MAP.items():
        if re.search(r"\b" + re.escape(key) + r"\b", source):
            return slug
    return make_slug(str(opportunity.get("niche", ""))) or "general"


def ensure_site_category(state, opportunity: dict) -> tuple:
    """Resolve and register the site category, creating it when missing.

    Returns (category_slug, created). New categories are upserted into the
    niches table so the site deployer includes them in every nav and the root
    index; created=True tells callers a brand-new hub must be deployed.
    """
    slug = resolve_site_category(opportunity)
    created = state.get_niche(slug) is None
    if created:
        state.upsert_niche(slug, slug.replace("-", " ").title(), category="Other")
        logger.info(f"Created site category for opportunity: {slug}")
    return slug, created


def score_opportunity(search_demand: int, buying_intent: float,
                      commission: float, competition: float) -> float:
    """Score an opportunity 0-1. Higher is better."""
    demand_norm = min(search_demand / 10000, 1.0)
    intent_norm = min(buying_intent, 1.0)
    commission_norm = min(commission / 100, 1.0)
    competition_norm = 1.0 - min(competition, 1.0)
    score = demand_norm * 0.3 + intent_norm * 0.3 + commission_norm * 0.2 + competition_norm * 0.2
    return round(score, 2)


class OpportunityScanner:
    """Scans for untapped affiliate opportunities."""

    def __init__(self, state, min_trend_score: int = 60, min_sources: int = 1):
        """Evidence gate for trend discovery.

        Only trends scoring at or above min_trend_score (0-100) that were also
        seen in at least min_sources providers become opportunities — a weak or
        single-source blip never mints a page.
        """
        self.state = state
        self.min_trend_score = min_trend_score
        self.min_sources = min_sources

    def discover_from_keywords(self, keywords: list[str],
                                base_demand: int = 1000,
                                base_intent: float = 0.5,
                                base_commission: float = 20.0) -> list[dict]:
        """Discover opportunities from a keyword list. Uses simulated data for Phase 3a."""
        results = []
        for kw in keywords:
            niche = kw.strip().lower()
            existing = self.state.get_opportunities("pending")
            if any(e["niche"] == niche for e in existing):
                continue
            score = score_opportunity(base_demand, base_intent, base_commission, 0.4)
            self.state.add_opportunity(niche, score, base_demand, base_intent, 0.4, base_commission)
            results.append({"niche": niche, "score": score})
            logger.info(f"Discovered opportunity: {niche} (score: {score})")
        return results

    def discover_from_trends(self, trends: list[dict],
                             max_opportunities: int = 3) -> list[dict]:
        """Turn real trending data into deploy opportunities (page + social posts).

        A trend becomes an opportunity only when it is a research-worthy guide
        (buying_guide/comparison) and the niche does not already have a pending
        opportunity or any posts on the site.
        """
        from ..trends.planner import ContentPlanner

        if not trends:
            return []
        planned = ContentPlanner().plan(trends, max_items=max_opportunities * 2)

        existing = self.state.get_opportunities("pending")
        existing_niches = set(n["slug"] for n in self.state.get_all_niches())

        results = []
        for item in planned:
            if item["content_type"] not in ("buying_guide", "comparison"):
                continue
            if item["score"] < self.min_trend_score:
                continue
            if len(item.get("sources") or []) < self.min_sources:
                continue
            source_cat = (item.get("category") or "").strip()
            site_cat = SITE_CATEGORY_MAP.get(source_cat.lower(), make_slug(source_cat)) if source_cat else "general"
            niche = self._slugify(item["product_name"]) or site_cat
            if any(e["niche"] == niche for e in existing) or niche in existing_niches:
                continue
            if len(results) >= max_opportunities:
                break
            score = self._trend_score(item["score"])
            self.state.add_opportunity(niche, score, search_volume=0,
                                       buying_intent=0.5, competition=0.4,
                                       commission=20.0, category=site_cat)
            results.append({
                "niche": niche,
                "product_name": item["product_name"],
                "category": site_cat,
                "source_category": source_cat,
                "score": round(item["score"], 1),
                "sources": item.get("sources", []),
            })
            logger.info(f"Trend discovery: {niche} -> category {site_cat} (trend score {item['score']})")
        return results

    def _slugify(self, name: str) -> str:
        return make_slug(name)

    def _trend_score(self, trend_score: int) -> float:
        """Map a trend score (0-100) onto the opportunity 0-1 scale."""
        score = min(max(trend_score / 100, 0.0), 1.0)
        return round(max(score, 0.5), 2)

    def discover_from_gsc_demand(self, data_dir=None, min_impressions: int = 100,
                                 min_clicks: int = 5, max_opportunities: int = 3) -> list[dict]:
        """Mint buying-guide opportunities from real Search Console demand.

        Demand is read from the top-performing URLs (page-level). A category
        whose /reviews/<segment>/ pages clear the impression/click floor gets a
        fresh annual buying guide — but only for segments that map onto the
        site's category taxonomy and have no pending opportunity or published
        page yet. On a young, lightly-trafficked site this is a strict no-op,
        which is correct: the bridge fires only on demand a human would act on.
        """
        from ..core.gsc_ingestor import category_evidence

        site_categories = {v for v in SITE_CATEGORY_MAP.values()}
        evidence = category_evidence(data_dir)
        if not evidence:
            return []

        existing = self.state.get_opportunities("pending")
        existing_slugs = set(n["slug"] for n in self.state.get_all_niches())
        year = datetime.now().year
        results = []

        for seg, ev in sorted(evidence.items()):
            if ev["impressions"] < min_impressions and ev["clicks"] < min_clicks:
                continue
            if seg not in site_categories:
                logger.info("GSC demand on non-category segment %s — skipped", seg)
                continue
            niche = make_slug(f"{seg.replace('-', ' ')} {year} buying guide")
            if any(e["niche"] == niche for e in existing) or niche in existing_slugs:
                continue
            if len(results) >= max_opportunities:
                break
            raw = score_opportunity(ev["impressions"], buying_intent=0.7,
                                    commission=20.0, competition=0.4)
            # Floor at 0.5 so a minted opportunity clears satisfies_evidence's
            # default cycle gate; demand beyond the floor lifts it further.
            score = round(max(raw, 0.5), 2)
            self.state.add_opportunity(niche, score, search_volume=ev["impressions"],
                                       buying_intent=0.7, competition=0.4,
                                       commission=20.0, category=seg)
            results.append({
                "niche": niche, "category": seg, "source_category": "gsc",
                "score": score,
                "impressions": ev["impressions"], "clicks": ev["clicks"],
            })
            logger.info(
                "GSC demand discovery: %s -> %s (imps %s, clicks %s)",
                niche, seg, ev["impressions"], ev["clicks"],
            )
        return results