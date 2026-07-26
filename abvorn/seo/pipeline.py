import logging
import json
from typing import Any

from .keywords import KeywordResearch
from .schema import SchemaBuilder
from .scoring import SEOContentScorer
from .linking import InternalLinker
from .trends import TrendDiscovery

logger = logging.getLogger("abvorn.seo.pipeline")


class SEOPipeline:
    def __init__(self, state=None):
        self.keyword_research = KeywordResearch()
        self.schema_builder = SchemaBuilder()
        self.scorer = SEOContentScorer()
        self.linker = InternalLinker(state)
        self.trend_discovery = TrendDiscovery()

    def run(self, content: dict, niche: str, persona: str = "") -> dict:
        result = dict(content)

        try:
            keywords = self.keyword_research.research_keywords(niche, persona)
            result["seo_keywords"] = keywords
        except Exception as e:
            logger.error(f"Keyword research failed: {e}")
            result["seo_keywords"] = []

        try:
            schema_markup = self.schema_builder.build_all(content)
            result["schema"] = schema_markup
        except Exception as e:
            logger.error(f"Schema building failed: {e}")
            result["schema"] = {}

        try:
            score_result = self.scorer.score_content(content, result.get("seo_keywords", []))
            result["seo_score"] = score_result["score"]
            result["seo_grade"] = score_result["grade"]
            result["seo_suggestions"] = score_result["suggestions"]
        except Exception as e:
            logger.error(f"SEO scoring failed: {e}")
            result["seo_score"] = 0
            result["seo_grade"] = "F"
            result["seo_suggestions"] = []

        try:
            internal_html = self.linker.build_internal_links_html(content, niche)
            result["internal_links_html"] = internal_html
        except Exception as e:
            logger.error(f"Internal linking failed: {e}")
            result["internal_links_html"] = ""

        try:
            base_keywords = [k.get("keyword", "") for k in result.get("seo_keywords", [])]
            trends = self.trend_discovery.discover_trends(base_keywords)
            result["trends"] = trends
        except Exception as e:
            logger.error(f"Trend discovery failed: {e}")
            result["trends"] = []

        try:
            result["seo_tags"] = self._build_seo_tags(result)
        except Exception as e:
            logger.error(f"SEO tags failed: {e}")
            result["seo_tags"] = ""

        return result

    def _build_seo_tags(self, enriched: dict) -> str:
        tags = []
        keywords = enriched.get("seo_keywords", [])
        if keywords:
            primary = keywords[0].get("keyword", "")
            if primary:
                tags.append(f'<meta name="keywords" content="{primary}">')

        schema_markup = enriched.get("schema", {})
        if schema_markup:
            for schema_type, schema_data in schema_markup.items():
                if isinstance(schema_data, dict):
                    tags.append(
                        f'<script type="application/ld+json">{json.dumps(schema_data, ensure_ascii=False)}</script>'
                    )

        return "\n".join(tags)
