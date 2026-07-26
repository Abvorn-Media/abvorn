import pytest, json
from unittest.mock import MagicMock
from abvorn.intel.patterns import PersuasionPattern, PersuasionPatternDB, PATTERN_TRIGGER, PATTERN_CTA, PATTERN_STRUCTURE, PATTERN_ANGLE
from abvorn.intel.extractor import PatternExtractor
from abvorn.intel.transfers import KnowledgeTransfer
from abvorn.intel.engine import CrossNicheIntelligence


class TestPersuasionPattern:
    def test_confidence_computation(self):
        p = PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets",
                               success_count=3, fail_count=1)
        assert p.confidence == 0.75

    def test_confidence_zero_when_no_attempts(self):
        p = PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets")
        assert p.confidence == 0.0

    def test_to_dict_includes_all_fields(self):
        p = PersuasionPattern(pattern_type="trigger", content="stop wasting",
                               source_niche="fitness", target_persona_trait="impatient",
                               success_count=5, fail_count=1, tags=["trigger", "fitness"])
        d = p.to_dict()
        assert d["pattern_type"] == "trigger"
        assert d["content"] == "stop wasting"
        assert d["source_niche"] == "fitness"
        assert d["target_persona_trait"] == "impatient"
        assert d["success_count"] == 5
        assert d["fail_count"] == 1
        assert d["confidence"] == 0.83
        assert d["tags"] == ["trigger", "fitness"]
        assert "pattern_id" in d
        assert "created_at" in d

    def test_auto_generates_id_and_timestamp(self):
        p = PersuasionPattern(pattern_type="cta", content="shop now", source_niche="tech")
        assert len(p.pattern_id) == 8
        assert p.created_at != ""


class TestPersuasionPatternDB:
    def test_store_and_retrieve(self):
        db = PersuasionPatternDB()
        p = PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets")
        stored = db.store(p)
        assert stored.pattern_id == p.pattern_id
        results = db.search(min_confidence=0.0)
        assert len(results) == 1
        assert results[0]["content"] == "buy now"

    def test_search_by_type(self):
        db = PersuasionPatternDB()
        db.store(PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets"))
        db.store(PersuasionPattern(pattern_type="trigger", content="finally", source_niche="gadgets"))
        db.store(PersuasionPattern(pattern_type="structure", content="list article", source_niche="gadgets"))
        results = db.search(pattern_type="cta", min_confidence=0.0)
        assert len(results) == 1
        assert results[0]["pattern_type"] == "cta"

    def test_search_by_niche(self):
        db = PersuasionPatternDB()
        db.store(PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets"))
        db.store(PersuasionPattern(pattern_type="cta", content="shop now", source_niche="fitness"))
        results = db.search(niche="gadgets", min_confidence=0.0)
        assert len(results) == 1
        assert results[0]["source_niche"] == "gadgets"

    def test_search_by_confidence(self):
        db = PersuasionPatternDB()
        p1 = PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets",
                                success_count=9, fail_count=1)
        p2 = PersuasionPattern(pattern_type="cta", content="shop now", source_niche="gadgets",
                                success_count=1, fail_count=9)
        db.store(p1)
        db.store(p2)
        results = db.search(min_confidence=0.7)
        assert len(results) == 1
        assert results[0]["content"] == "buy now"

    def test_record_outcome_success(self):
        db = PersuasionPatternDB()
        p = PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets",
                               success_count=3, fail_count=1)
        db.store(p)
        db.record_outcome(p.pattern_id, succeeded=True)
        assert p.success_count == 4
        assert p.fail_count == 1

    def test_record_outcome_failure(self):
        db = PersuasionPatternDB()
        p = PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets",
                               success_count=3, fail_count=1)
        db.store(p)
        db.record_outcome(p.pattern_id, succeeded=False)
        assert p.success_count == 3
        assert p.fail_count == 2

    def test_get_transferable(self):
        db = PersuasionPatternDB()
        db.store(PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets",
                                    success_count=9, fail_count=1))
        db.store(PersuasionPattern(pattern_type="trigger", content="finally", source_niche="gadgets",
                                    success_count=8, fail_count=2))
        db.store(PersuasionPattern(pattern_type="cta", content="join now", source_niche="fitness",
                                    success_count=5, fail_count=5))
        results = db.get_transferable("gadgets", "fitness", limit=2)
        assert len(results) == 2
        for r in results:
            assert r["source_niche"] == "gadgets"

    def test_count_and_stats(self):
        db = PersuasionPatternDB()
        assert db.count() == 0
        stats = db.get_stats()
        assert stats["total"] == 0

        db.store(PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets",
                                    success_count=5, fail_count=1))
        db.store(PersuasionPattern(pattern_type="trigger", content="finally", source_niche="gadgets",
                                    success_count=3, fail_count=1))
        db.store(PersuasionPattern(pattern_type="cta", content="shop now", source_niche="fitness",
                                    success_count=2, fail_count=2))
        assert db.count() == 3
        stats = db.get_stats()
        assert stats["total"] == 3
        assert stats["by_type"]["cta"] == 2
        assert stats["by_type"]["trigger"] == 1
        assert stats["avg_confidence"] > 0
        assert len(stats["top_niches"]) == 2

    def test_duplicate_pattern_dedup(self):
        db = PersuasionPatternDB()
        p1 = PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets",
                                success_count=3, fail_count=1)
        p2 = PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets",
                                success_count=2, fail_count=0)
        db.store(p1)
        db.store(p2)
        assert db.count() == 1
        stored = list(db._patterns.values())[0]
        assert stored.success_count == 5
        assert stored.fail_count == 1

    def test_empty_db_edge_case(self):
        db = PersuasionPatternDB()
        assert db.search() == []
        assert db.get_high_confidence() == []
        assert db.get_transferable("gadgets", "fitness") == []
        assert db.count() == 0
        assert db.get_stats() == {"total": 0, "by_type": {}, "avg_confidence": 0, "top_niches": []}


class TestPatternExtractor:
    def test_extract_cta_patterns(self):
        extractor = PatternExtractor()
        content = {
            "article_html": "<p>Buy now and save big! Shop now for limited deals.</p>",
            "niche": "gadgets",
            "selected_angle": "best value"
        }
        patterns = extractor.extract_from_content(content, outcome=True)
        cta_patterns = [p for p in patterns if p.pattern_type == PATTERN_CTA]
        assert len(cta_patterns) >= 1
        assert any("buy now" in c.content for c in cta_patterns)

    def test_extractor_angle_pattern(self):
        extractor = PatternExtractor()
        content = {
            "article_html": "<p>Great product review here.</p>",
            "niche": "gadgets",
            "selected_angle": "budget friendly option"
        }
        patterns = extractor.extract_from_content(content, outcome=True)
        angle_patterns = [p for p in patterns if p.pattern_type == PATTERN_ANGLE]
        assert len(angle_patterns) == 1
        assert angle_patterns[0].content == "budget friendly option"

    def test_extractor_structure_pattern(self):
        extractor = PatternExtractor()
        content = {
            "article_html": "<h2>Introduction</h2><p>text</p><h3>Key Features</h3><p>text</p><h2>Comparison</h2><p>text</p>",
            "niche": "gadgets",
            "selected_angle": "best pick"
        }
        patterns = extractor.extract_from_content(content, outcome=True)
        struct_patterns = [p for p in patterns if p.pattern_type == PATTERN_STRUCTURE]
        assert len(struct_patterns) == 1

    def test_extract_from_persona(self):
        extractor = PatternExtractor()
        persona = {
            "niche": "fitness",
            "psychology": {
                "anxieties": ["getting injured", "wasting money on bad gear"],
                "desires": ["look good", "feel confident"],
                "decision_trigger": "fear of missing out"
            }
        }
        patterns = extractor.extract_from_persona(persona)
        assert len(patterns) >= 4
        anxiety_patterns = [p for p in patterns if "anxiety" in p.tags]
        desire_patterns = [p for p in patterns if "desire" in p.tags]
        assert len(anxiety_patterns) >= 1
        assert len(desire_patterns) >= 1

    def test_extract_niche_similarity(self):
        extractor = PatternExtractor()
        db = PersuasionPatternDB()
        db.store(PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets",
                                    success_count=5, fail_count=0))
        db.store(PersuasionPattern(pattern_type="cta", content="buy now", source_niche="tech",
                                    success_count=3, fail_count=0))
        db.store(PersuasionPattern(pattern_type="trigger", content="finally", source_niche="gadgets",
                                    success_count=4, fail_count=0))
        sim = extractor.extract_niche_similarity("gadgets", "tech", db)
        assert sim > 0
        assert sim <= 1.0

    def test_extract_niche_similarity_no_db(self):
        extractor = PatternExtractor()
        assert extractor.extract_niche_similarity("a", "b", None) == 0.0


class TestKnowledgeTransfer:
    def test_find_related_niches(self):
        db = PersuasionPatternDB()
        db.store(PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets",
                                    success_count=5, fail_count=0, target_persona_trait="impulsive"))
        db.store(PersuasionPattern(pattern_type="cta", content="buy now", source_niche="fashion",
                                    success_count=3, fail_count=0, target_persona_trait="impulsive"))
        db.store(PersuasionPattern(pattern_type="trigger", content="finally", source_niche="gadgets",
                                    success_count=4, fail_count=0, target_persona_trait="impatient"))
        db.store(PersuasionPattern(pattern_type="trigger", content="finally", source_niche="books",
                                    success_count=2, fail_count=0, target_persona_trait="impatient"))

        transfer = KnowledgeTransfer(db)
        related = transfer.find_related_niches("gadgets", ["fashion", "books", "unknown"])
        assert len(related) >= 1
        niches_found = [r["niche"] for r in related]
        assert "fashion" in niches_found or "books" in niches_found

    def test_transfer_patterns(self):
        db = PersuasionPatternDB()
        db.store(PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets",
                                    success_count=9, fail_count=1))
        db.store(PersuasionPattern(pattern_type="trigger", content="finally", source_niche="gadgets",
                                    success_count=8, fail_count=2))
        db.store(PersuasionPattern(pattern_type="cta", content="shop now", source_niche="fitness",
                                    success_count=5, fail_count=5))

        transfer = KnowledgeTransfer(db)
        transferred = transfer.transfer_patterns("gadgets", "fitness", limit=1)
        assert len(transferred) == 1
        assert transferred[0]["source_niche"] == "gadgets"

    def test_build_cross_niche_prompt(self):
        db = PersuasionPatternDB()
        db.store(PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets",
                                    success_count=9, fail_count=1))
        db.store(PersuasionPattern(pattern_type="trigger", content="finally", source_niche="gadgets",
                                    success_count=1, fail_count=8,
                                    target_persona_trait="impatient"))

        transfer = KnowledgeTransfer(db)
        prompt = transfer.build_cross_niche_prompt("gadgets")
        assert "[CROSS-NICHE INTELLIGENCE]" in prompt
        assert "buy now" in prompt

    def test_build_cross_niche_prompt_empty_db(self):
        transfer = KnowledgeTransfer(PersuasionPatternDB())
        assert transfer.build_cross_niche_prompt("gadgets") == ""

    def test_compute_pattern_overlap(self):
        db = PersuasionPatternDB()
        db.store(PersuasionPattern(pattern_type="cta", content="buy now", source_niche="gadgets"))
        db.store(PersuasionPattern(pattern_type="cta", content="buy now", source_niche="tech"))
        db.store(PersuasionPattern(pattern_type="trigger", content="finally", source_niche="gadgets"))
        transfer = KnowledgeTransfer(db)
        overlap = transfer.compute_pattern_overlap("gadgets", "tech")
        assert overlap > 0
        assert overlap <= 1.0


class TestCrossNicheIntelligence:
    def test_ingest_cycle(self):
        engine = CrossNicheIntelligence()
        content = {
            "article_html": "<h2>Review</h2><p>Buy now and save!</p>",
            "niche": "gadgets",
            "selected_angle": "best value pick"
        }
        persona = {
            "niche": "gadgets",
            "psychology": {
                "anxieties": ["overpaying"],
                "desires": ["getting the best"],
                "decision_trigger": "value_seeker"
            }
        }
        result = engine.ingest_cycle(content, persona, outcome_success=True)
        assert result["patterns_extracted"] >= 3
        assert result["patterns_stored"] >= 3
        assert result["total_patterns"] >= 3

    def test_prepare_prompt(self):
        engine = CrossNicheIntelligence()
        content = {
            "article_html": "<h2>Review</h2><p>Buy now - you deserve this!</p>",
            "niche": "gadgets",
            "selected_angle": "premium pick"
        }
        persona = {
            "niche": "gadgets",
            "psychology": {
                "anxieties": ["bad quality"],
                "desires": ["premium feel"],
                "decision_trigger": "quality_obsessed"
            }
        }
        engine.ingest_cycle(content, persona, outcome_success=True)
        prompt = engine.prepare_prompt("gadgets", persona)
        assert "[CROSS-NICHE INTELLIGENCE]" in prompt

    def test_intelligence_report(self):
        engine = CrossNicheIntelligence()
        content = {
            "article_html": "<h2>Review</h2><p>Shop now!</p>",
            "niche": "gadgets",
            "selected_angle": "top rated"
        }
        persona = {"niche": "gadgets", "psychology": {"anxieties": ["choices"], "desires": ["simplicity"]}}
        engine.ingest_cycle(content, persona)
        report = engine.get_intelligence_report()
        assert "CROSS-NICHE INTELLIGENCE REPORT" in report
        assert "Total Patterns:" in report

    def test_learning_velocity(self):
        engine = CrossNicheIntelligence()
        assert engine.get_learning_velocity() == {"patterns_per_cycle": 0, "total_cycles": 0, "total_patterns": 0}

        content = {
            "article_html": "<h2>Test</h2><p>Click here!</p>",
            "niche": "gadgets",
            "selected_angle": "test angle"
        }
        persona = {"niche": "gadgets", "psychology": {"anxieties": ["x"], "desires": ["y"]}}
        engine.ingest_cycle(content, persona)
        vel = engine.get_learning_velocity()
        assert vel["total_cycles"] == 1
        assert vel["total_patterns"] > 0
        assert vel["patterns_per_cycle"] > 0

    def test_state_persistence(self):
        mock_state = MagicMock()
        engine = CrossNicheIntelligence(state=mock_state)
        content = {
            "article_html": "<p>Buy now!</p>",
            "niche": "gadgets",
            "selected_angle": "test"
        }
        persona = {"niche": "gadgets", "psychology": {"anxieties": ["x"], "desires": ["y"]}}
        engine.ingest_cycle(content, persona)
        mock_state.upsert_intel_pattern.assert_called()
        mock_state.set_meta.assert_called()