import json, logging
from datetime import datetime
from abvorn.agents.researcher import research_niche
from abvorn.agents.writer import generate_outline, write_draft
from abvorn.agents.editor import fact_check, polish, build_schema

logger = logging.getLogger("abvorn.pipeline")

class ContentPipeline:

    def __init__(self, state=None):
        self.state = state

    def run(self, niche: str, router, persona: dict = None,
            existing_products: list = None) -> dict:
        """Full pipeline: RESEARCH -> OUTLINE -> DRAFT -> FACT-CHECK -> POLISH"""
        # Stage 1: RESEARCH
        logger.info(f"[PIPELINE] RESEARCH: {niche}")
        products = existing_products or research_niche(niche, router)
        if not products:
            logger.error(f"[PIPELINE] RESEARCH failed for {niche}")
            return None

        # Stage 2: OUTLINE
        logger.info(f"[PIPELINE] OUTLINE: {niche}")
        outline = generate_outline(niche, products, persona or {}, router)
        if not outline or not outline.get("outline"):
            logger.warning(f"[PIPELINE] OUTLINE empty for {niche}, using default")
            outline = {"outline": ["H2: Introduction", "H2: Product Reviews", "H2: Buying Guide", "H2: FAQ", "H2: Conclusion"],
                       "selected_angle": "problem_solution", "primary_keyword": f"best {niche}"}

        # Stage 3: DRAFT
        logger.info(f"[PIPELINE] DRAFT: {niche}")
        draft = write_draft(niche, products, outline, persona or {}, products, router)
        if not draft:
            logger.error(f"[PIPELINE] DRAFT failed for {niche}")
            return None

        # Stage 4: FACT-CHECK
        logger.info(f"[PIPELINE] FACT-CHECK: {niche}")
        fc_result = fact_check(draft, products, router)
        if fc_result and not fc_result.get("passed") and fc_result.get("issues"):
            for issue in fc_result["issues"][:3]:
                logger.warning(f"  Fact-check issue [{issue.get('severity','low')}]: {issue.get('claim','')[:80]}")

        # Stage 5: POLISH
        logger.info(f"[PIPELINE] POLISH: {niche}")
        polished = polish(draft, fc_result or {}, persona or {}, router)

        # Combine results
        final_intro = polished.get("revised_intro") or fc_result.get("revised_intro") or draft.get("intro", "")
        final_article = polished.get("revised_article") or fc_result.get("revised_article") or draft.get("article_html", "")
        quality = polished.get("quality_score", {"overall": 7.0})
        schema_data = polished.get("schema_markup", {}) or {}

        faqs = draft.get("faqs", [])
        faq_pairs = [(f.get("question", ""), f.get("answer", "")) for f in faqs if isinstance(f, dict)]

        dummy_url = f"https://example.com/best-{niche.replace(' ', '-')}"
        schema = build_schema(
            title=draft.get("post_title", f"Best {niche}"),
            description=draft.get("meta_description", f"Best {niche} buying guide"),
            url=dummy_url,
            image=f"{dummy_url}/featured-image.jpg",
            date_published=datetime.now().isoformat(),
            products=products,
            faqs=faq_pairs
        )

        return {
            "post_title": draft.get("post_title", f"Best {niche} — Expert Review"),
            "meta_description": draft.get("meta_description", f"Find the best {niche} with our expert guide."),
            "intro": final_intro,
            "article_html": final_article,
            "products": products,
            "faqs": faq_pairs,
            "tags": draft.get("tags", [niche, "buying guide"]),
            "lead_magnet_title": draft.get("lead_magnet_title", f"Ultimate {niche} Checklist"),
            "lead_magnet_description": draft.get("lead_magnet_description", "Get our expert checklist."),
            "socials": draft.get("socials", {}),
            "quality_score": quality.get("overall", 7.0),
            "quality_details": quality,
            "schema": schema,
            "selected_angle": outline.get("selected_angle", "problem_solution"),
            "primary_keyword": outline.get("primary_keyword", f"best {niche}"),
        }
