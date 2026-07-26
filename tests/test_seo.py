import json
import tempfile
from pathlib import Path

import pytest

from abvorn.seo.keywords import KeywordResearch
from abvorn.seo.schema import SchemaBuilder
from abvorn.seo.scoring import SEOContentScorer, SEO_WEIGHTS
from abvorn.seo.linking import InternalLinker
from abvorn.seo.trends import TrendDiscovery
from abvorn.seo.pipeline import SEOPipeline

SAMPLE_CONTENT = {
    "post_title": "Best Wireless Headphones for Commuters in 2026",
    "meta_description": "We tested 20+ pairs of wireless headphones to find the perfect pair for your daily commute. Our top picks offer noise cancelling, long battery life, and comfort.",
    "intro": "<p>Finding the right headphones for your commute can transform your day.</p>",
    "article_html": (
        "<h1>Best Wireless Headphones for Commuters</h1>"
        "<p>After testing 20+ pairs of wireless headphones, we found the best options for commuting.</p>"
        "<h2>How We Tested</h2>"
        "<p>We spent 40 hours testing noise cancelling, battery life, and comfort.</p>"
        "<ul><li>Tested on trains</li><li>Tested on buses</li><li>Tested in coffee shops</li></ul>"
        "<h2>Top Pick: Sony WH-1000XM5</h2>"
        "<p>The best wireless headphones for commuters are the Sony WH-1000XM5.</p>"
        "<h2>Budget Option</h2><p>The Anker Soundcore Q45 offers great value.</p>"
        "<h2>Comparison</h2><p>See how they stack up.</p>"
    ),
    "tags": ["wireless headphones", "commuter", "buying guide"],
    "niche": "wireless headphones",
    "persona_name": "Marcus the Commuter",
}


class TestKeywordResearch:
    def test_research_returns_correct_structure(self):
        kr = KeywordResearch()
        results = kr.research_keywords("wireless headphones", "Marcus the Commuter")
        assert len(results) >= 5
        for item in results:
            assert "keyword" in item
            assert "volume" in item
            assert "difficulty" in item
            assert "intent" in item
            assert "long_tail" in item
            assert isinstance(item["volume"], int)
            assert isinstance(item["difficulty"], float)
            assert 0.0 <= item["difficulty"] <= 1.0
            assert item["intent"] in ("informational", "commercial", "transactional", "navigational")

    def test_research_returns_primary_keyword_first(self):
        kr = KeywordResearch()
        results = kr.research_keywords("wireless headphones")
        assert results[0]["keyword"] == "best wireless headphones"
        assert results[0]["intent"] == "commercial"

    def test_extract_long_tail_returns_variants(self):
        kr = KeywordResearch()
        variants = kr.extract_long_tail("noise cancelling headphones")
        assert len(variants) >= 3
        assert all(isinstance(v, str) for v in variants)

    def test_research_fallback_for_unknown_niche(self):
        kr = KeywordResearch()
        results = kr.research_keywords("quantum widgets")
        assert len(results) >= 4


class TestSchemaBuilder:
    def test_build_article_schema(self):
        sb = SchemaBuilder()
        schema = sb.build_article_schema(SAMPLE_CONTENT)
        assert schema["@type"] == "Article"
        assert schema["headline"] == SAMPLE_CONTENT["post_title"]
        assert schema["description"] == SAMPLE_CONTENT["meta_description"]
        assert schema["@context"] == "https://schema.org"

    def test_build_product_schema(self):
        sb = SchemaBuilder()
        schema = sb.build_product_schema("Sony WH-1000XM5", price=349.99, rating=4.5)
        assert schema["@type"] == "Product"
        assert schema["name"] == "Sony WH-1000XM5"
        assert schema["offers"]["price"] == 349.99
        assert schema["aggregateRating"]["ratingValue"] == 4.5

    def test_build_product_schema_minimal(self):
        sb = SchemaBuilder()
        schema = sb.build_product_schema("Test Product")
        assert schema["@type"] == "Product"
        assert "offers" not in schema
        assert "aggregateRating" not in schema

    def test_build_faq_schema(self):
        sb = SchemaBuilder()
        qa = [
            {"question": "Are they comfortable?", "answer": "Yes, very comfortable."},
            {"question": "How long does battery last?", "answer": "Up to 30 hours."},
        ]
        schema = sb.build_faq_schema(qa)
        assert schema["@type"] == "FAQPage"
        assert len(schema["mainEntity"]) == 2

    def test_build_howto_schema(self):
        sb = SchemaBuilder()
        steps = [
            {"name": "Step 1", "text": "Do this first."},
            {"name": "Step 2", "text": "Then do this."},
        ]
        schema = sb.build_howto_schema(steps)
        assert schema["@type"] == "HowTo"
        assert len(schema["step"]) == 2

    def test_build_all_detects_article(self):
        sb = SchemaBuilder()
        schemas = sb.build_all(SAMPLE_CONTENT)
        assert "article" in schemas
        assert schemas["article"]["@type"] == "Article"

    def test_schema_is_valid_json_ld(self):
        sb = SchemaBuilder()
        schema = sb.build_article_schema(SAMPLE_CONTENT)
        dumped = json.dumps(schema)
        parsed = json.loads(dumped)
        assert parsed["@context"] == "https://schema.org"


class TestSEOContentScorer:
    def test_good_content_scores_above_zero(self):
        scorer = SEOContentScorer()
        keywords = [{"keyword": "wireless headphones"}] * 5
        result = scorer.score_content(SAMPLE_CONTENT, keywords)
        assert result["score"] > 0

    def test_empty_content_gets_grade_f(self):
        scorer = SEOContentScorer()
        result = scorer.score_content({}, [])
        assert result["grade"] == "F"
        assert result["score"] <= 30

    def test_weights_sum_to_one(self):
        total = sum(SEO_WEIGHTS.values())
        assert total == 1.0

    def test_suggestions_list_returned(self):
        scorer = SEOContentScorer()
        result = scorer.score_content({}, [])
        assert isinstance(result["suggestions"], list)
        assert len(result["suggestions"]) > 0

    def test_details_contains_all_keys(self):
        scorer = SEOContentScorer()
        keywords = [{"keyword": "test"}]
        result = scorer.score_content(SAMPLE_CONTENT, keywords)
        for key in SEO_WEIGHTS:
            assert key in result["details"]

    def test_score_ranges(self):
        scorer = SEOContentScorer()
        result = scorer.score_content(SAMPLE_CONTENT, [{"keyword": "wireless headphones"}])
        assert 0 <= result["score"] <= 100


class TestInternalLinker:
    def test_handle_empty_state_gracefully(self):
        linker = InternalLinker(state=None)
        links = linker.suggest_links(SAMPLE_CONTENT, "wireless headphones")
        assert links == []

    def test_handle_empty_posts(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            from abvorn.core.state import AbvornState
            state = AbvornState(db_path)
            linker = InternalLinker(state)
            links = linker.suggest_links(SAMPLE_CONTENT, "wireless headphones")
            assert links == []
            state.close()

    def test_build_internal_links_html_returns_empty_with_no_state(self):
        linker = InternalLinker(state=None)
        html = linker.build_internal_links_html(SAMPLE_CONTENT, "wireless headphones")
        assert html == ""


class TestTrendDiscovery:
    def test_discover_returns_results(self):
        td = TrendDiscovery()
        results = td.discover_trends(["wireless headphones", "noise cancelling"])
        assert len(results) >= 4

    def test_trend_has_correct_structure(self):
        td = TrendDiscovery()
        results = td.discover_trends(["wireless headphones"])
        for trend in results:
            assert "topic" in trend
            assert "growth_rate" in trend
            assert trend["growth_rate"] in ("rising", "peaking", "declining")
            assert "momentum_score" in trend
            assert 0.0 <= trend["momentum_score"] <= 1.0
            assert "related_queries" in trend

    def test_calculate_opportunity_score(self):
        td = TrendDiscovery()
        trend = {"momentum_score": 0.8, "growth_rate": "rising"}
        score = td.calculate_opportunity_score(trend)
        assert 0 <= score <= 100


class TestSEOPipeline:
    def test_run_enriches_content_dict(self):
        pipeline = SEOPipeline()
        result = pipeline.run(SAMPLE_CONTENT, "wireless headphones", "Marcus the Commuter")
        assert "seo_keywords" in result
        assert "seo_score" in result
        assert "seo_suggestions" in result
        assert "schema" in result
        assert "internal_links_html" in result
        assert "seo_tags" in result
        assert "trends" in result

    def test_run_does_not_modify_original(self):
        original = dict(SAMPLE_CONTENT)
        pipeline = SEOPipeline()
        result = pipeline.run(SAMPLE_CONTENT, "wireless headphones")
        assert SAMPLE_CONTENT == original

    def test_run_with_empty_content(self):
        pipeline = SEOPipeline()
        result = pipeline.run({}, "unknown niche")
        assert "seo_keywords" in result
        assert "seo_score" in result

    def test_run_handles_missing_fields(self):
        pipeline = SEOPipeline()
        result = pipeline.run({"post_title": "Test"}, "test")
        assert result["post_title"] == "Test"

    def test_seo_tags_contains_keywords(self):
        pipeline = SEOPipeline()
        result = pipeline.run(SAMPLE_CONTENT, "wireless headphones")
        assert "keywords" in result["seo_tags"] or result["seo_tags"] == ""

    def test_run_no_state_graceful(self):
        pipeline = SEOPipeline()
        result = pipeline.run(SAMPLE_CONTENT, "wireless headphones")
        assert result["internal_links_html"] == ""
