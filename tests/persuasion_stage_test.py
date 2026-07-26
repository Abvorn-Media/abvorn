"""Tests for BuyingStageDetector."""
import pytest
from abvorn.persuasion.stage import BuyingStage, detect_stage


def test_awareness_from_title():
    content = {"title": "What is 4K TV? A Complete Guide", "article_html": "<p>4K TVs have four times the pixels...</p>"}
    assert detect_stage(content) == BuyingStage.AWARENESS


def test_consideration_from_title():
    content = {"title": "Best Wireless Headphones of 2026", "article_html": "<p>We tested 20 pairs...</p>"}
    assert detect_stage(content) == BuyingStage.CONSIDERATION


def test_decision_from_title():
    content = {"title": "Buy Samsung QN90A — Best Price Today", "article_html": "<p>Where to buy the QN90A...</p>"}
    assert detect_stage(content) == BuyingStage.DECISION


def test_awareness_from_content():
    content = {"title": "TV Technology Explained", "article_html": "<p>A guide to understanding different types of TV panels...</p>"}
    assert detect_stage(content) == BuyingStage.AWARENESS


def test_consideration_from_content():
    content = {"title": "Top Rated Monitors", "article_html": "<p>Comparison of the top 10 monitors for 2026...</p>"}
    assert detect_stage(content) == BuyingStage.CONSIDERATION


def test_decision_from_content():
    content = {"title": "Monitor Discounts", "article_html": "<p>Best price on the LG UltraGear — save $200 today...</p>"}
    assert detect_stage(content) == BuyingStage.DECISION


def test_empty_content_defaults_to_awareness():
    content = {"title": "", "article_html": ""}
    assert detect_stage(content) == BuyingStage.AWARENESS
