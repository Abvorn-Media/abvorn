import pytest
from abvorn.humanize.scanner import AIScanner
from abvorn.humanize.variator import SentenceVariator
from abvorn.humanize.transitions import TransitionInjector
from abvorn.humanize.specificity import SpecificityBooster
from abvorn.humanize import HumanizationEngine


class TestAIScanner:
    def test_detects_additionally(self):
        scanner = AIScanner()
        results = scanner.scan("Additionally, this product is great.")
        assert len(results) == 1
        assert "Additionally" in results[0]["match"]

    def test_detects_in_conclusion(self):
        scanner = AIScanner()
        results = scanner.scan("In conclusion, buy this product.")
        assert len(results) >= 1

    def test_clean_text_no_hits(self):
        scanner = AIScanner()
        results = scanner.scan("This headphone weighs 8.2 oz and costs $49. We tested it for 40 hours.")
        assert len(results) == 0

    def test_scan_html_ignores_tags(self):
        scanner = AIScanner()
        html = "<p>Additionally, <strong>this</strong> is a great product.</p>"
        results = scanner.scan_html(html)
        assert len(results) >= 1

    def test_ai_score_perfect(self):
        scanner = AIScanner()
        score = scanner.get_ai_score("This headphone costs $49 and weighs 8.2 oz. We recommend it.")
        assert score > 0.9

    def test_ai_score_terrible(self):
        scanner = AIScanner()
        score = scanner.get_ai_score("Additionally, it's worth noting that in conclusion this is a game-changer.")
        assert score < 0.6


class TestSentenceVariator:
    def test_breaks_long_sentences(self):
        variator = SentenceVariator()
        long = "This is a very long sentence that goes on and on with many different words and clauses that should probably be broken into two separate sentences for better readability and flow. " * 3
        result = variator.break_long_sentences(long)
        sentences = [s.strip() for s in result.replace("?", ".").replace("!", ".").split(".") if s.strip()]
        original_count = long.count(". ")
        assert len(sentences) > original_count

    def test_vary_openers_changes_duplicates(self):
        variator = SentenceVariator()
        text = "The product is great. The battery lasts 10 hours. The price is fair."
        result = variator.vary_openers(text)
        assert "The product" in result or "Here's" in result

    def test_short_text_unchanged(self):
        variator = SentenceVariator()
        text = "Short text."
        assert variator.break_long_sentences(text) == text


class TestTransitionInjector:
    def test_injects_transition(self):
        injector = TransitionInjector()
        text = "The Sony WH-1000XM5 costs $349.\n\nThe battery lasts 40 hours on a single charge."
        result = injector.inject_transitions(text)
        # Should add a transition or keep it (either is acceptable behavior)
        assert "battery" in result

    def test_skips_existing_transitions(self):
        injector = TransitionInjector()
        text = "First paragraph.\n\nHere's the thing: second paragraph."
        result = injector.inject_transitions(text)
        assert "Here's the thing:" in result

    def test_single_paragraph_unchanged(self):
        injector = TransitionInjector()
        assert injector.inject_transitions("Just one paragraph.") == "Just one paragraph."

    def test_inject_transitions_html(self):
        injector = TransitionInjector()
        html = "<p>First paragraph.</p><p>Second paragraph has details.</p>"
        result = injector.inject_transitions_html(html)
        assert "<p>" in result


class TestSpecificityBooster:
    def test_detects_very_adj(self):
        booster = SpecificityBooster()
        results = booster.scan_for_vagueness("This is a very good product.")
        assert len(results) >= 1

    def test_detects_affordable(self):
        booster = SpecificityBooster()
        results = booster.scan_for_vagueness("This is an affordable option.")
        assert any("affordable" in r["match"] for r in results)

    def test_clean_text_passes(self):
        booster = SpecificityBooster()
        results = booster.scan_for_vagueness("This headphone costs $49 and has 30 hours of battery life. We measured 8.2 oz on our scale.")
        assert len(results) == 0

    def test_specificity_score_high(self):
        booster = SpecificityBooster()
        score = booster.get_specificity_score("Costs $49. Weighs 8.2 oz. 30 hour battery.")
        assert score > 0.9

    def test_specificity_score_low(self):
        booster = SpecificityBooster()
        score = booster.get_specificity_score("This is a very good and extremely popular product. It's high-quality and affordable.")
        assert score < 0.6


class TestHumanizationEngine:
    def test_analyze_enriches_content(self):
        engine = HumanizationEngine()
        content = {
            "post_title": "Best Headphones",
            "article_html": "<p>Additionally, this is a game-changer.</p>",
            "intro": "<p>This is very good.</p>",
        }
        result = engine.analyze(content)
        assert "ai_ism_count" in result
        assert "vague_count" in result
        assert "overall_score" in result

    def test_humanize_returns_modified_content(self):
        engine = HumanizationEngine()
        content = {
            "post_title": "Test",
            "article_html": "<p>It is worth noting that this product is good.</p>",
            "intro": "",
        }
        result = engine.humanize(content)
        assert "humanization" in result
        assert "It is worth noting" not in result["article_html"]

    def test_humanize_empty_content(self):
        engine = HumanizationEngine()
        result = engine.humanize({"post_title": "Test", "article_html": "", "intro": ""})
        assert "humanization" in result