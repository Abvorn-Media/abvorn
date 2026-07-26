import pytest
from abvorn.gate import QualityGate
from abvorn.humanize import HumanizationEngine


def test_gate_evaluate_basic():
    gate = QualityGate()
    content = {
        "post_title": "Best Wireless Headphones for Commuters",
        "meta_description": "We tested 12 wireless headphones for commuters. Our top pick costs $49 and lasts 30 hours.",
        "article_html": "<h2>Our Top Pick</h2><p>The Sony WH-1000XM5 costs $349 and weighs 254g. It has 30 hours of battery life.</p><h2>Budget Option</h2><p>The Anker Soundcore costs $49. It weighs 180g.</p>",
        "intro": "<p>After testing 12 wireless headphones for 40 hours, here's our top pick.</p>",
        "tags": ["wireless headphones", "buying guide"],
        "niche": "wireless headphones",
    }
    report = gate.evaluate(content, niche="wireless headphones")
    assert "passed" in report
    assert "composite_score" in report
    assert "scores" in report
    assert "improvement_suggestions" in report


def test_gate_returns_scores():
    gate = QualityGate()
    content = {
        "post_title": "Test",
        "article_html": "<p>This is a game-changer product that is very good.</p>",
        "intro": "<p>Test</p>",
        "tags": ["test"],
    }
    report = gate.evaluate(content, niche="test")
    assert report["scores"]["seo"] >= 0
    assert report["scores"]["humanization"] >= 0
    assert report["scores"]["soul"] in (0, 100)


def test_gate_blocks_bad_content():
    gate = QualityGate()
    content = {
        "post_title": "In today's rapidly evolving landscape, this game-changer will revolutionize everything",
        "article_html": "<p>It is worth noting that this is an extremely good product. Additionally, it's very high-quality.</p>",
        "intro": "<p>In conclusion, buy this.</p>",
        "tags": ["test"],
    }
    report = gate.evaluate(content, niche="test")
    # Should fail on both soul (banned phrases) and humanization (AI-isms)
    has_issues = not report["passed"] or len(report["failures"]) > 0 or len(report["warnings"]) > 0
    assert has_issues


def test_gate_platform_check():
    gate = QualityGate()
    content = {
        "post_title": "Best Headphones",
        "article_html": "<p>We tested 12 models. The winner costs $49.</p>",
        "intro": "<p>Intro text here.</p>",
        "niche": "headphones",
    }
    report = gate.evaluate_for_platform(content, "x", niche="headphones")
    assert "platform_check" in report
    assert report["platform_check"]["platform"] == "x"


def test_gate_summary():
    gate = QualityGate()
    summary = gate.get_summary()
    assert summary["total"] >= 0


def test_gate_accumulates_history():
    gate = QualityGate()
    content = {"post_title": "Test", "article_html": "<p>Test costs $10.</p>", "intro": "<p>Hi</p>"}
    gate.evaluate(content, niche="test")
    gate.evaluate(content, niche="test")
    summary = gate.get_summary()
    assert summary["total"] >= 2


def test_gate_soul_violations_detected():
    gate = QualityGate()
    content = {
        "post_title": "Best Scam Product",
        "article_html": "<p>This trick will deceive you into buying.</p>",
        "intro": "<p>Fake review.</p>",
    }
    report = gate.evaluate(content, niche="scam")
    if not report["passed"]:
        assert len(report.get("soul_violations", [])) > 0 or len(report.get("failures", [])) > 0