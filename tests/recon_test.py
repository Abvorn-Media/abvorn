"""Tests for trend recon providers — mocked network calls for speed."""
import pytest
from unittest.mock import MagicMock, patch
from abvorn.trends.recon.providers import (
    DuckDuckGoSource, AmazonSource, RedditSource, GoogleTrendsSource
)


def test_duckduckgo_initializes():
    s = DuckDuckGoSource()
    assert s is not None


@patch("abvorn.trends.recon.providers.DDGS")
def test_duckduckgo_search_returns_list(MockDDGS):
    mock_instance = MagicMock()
    mock_instance.text.return_value = [
        {"title": "Best TVs 2026", "body": "The Samsung S95H OLED is amazing", "href": "https://example.com/1"},
        {"title": "Top Rated TVs", "body": "LG C5 Series OLED TV review", "href": "https://example.com/2"},
    ]
    MockDDGS.return_value = mock_instance
    s = DuckDuckGoSource()
    s._ddgs = mock_instance
    results = s.search("tv")
    assert isinstance(results, list)
    assert len(results) > 0


@patch("abvorn.trends.recon.providers.DDGS")
def test_duckduckgo_results_have_required_keys(MockDDGS):
    mock_instance = MagicMock()
    mock_instance.text.return_value = [
        {"title": "Samsung S95H OLED", "body": "The Samsung S95H OLED is great", "href": "https://example.com/1"},
    ]
    MockDDGS.return_value = mock_instance
    s = DuckDuckGoSource()
    s._ddgs = mock_instance
    results = s.search("tv")
    if results:
        r = results[0]
        assert "product_name" in r
        assert "source" in r
        assert "score" in r


def test_amazon_initializes():
    s = AmazonSource()
    assert s is not None


@patch("requests.get")
def test_amazon_search_returns_list(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.text = '<div class="p13n-sc-uncoverable-faceout"><div class="_cDEzb_p13n-sc-css-line-clamp-3_g3dy1">Samsung TV</div></div>'
    s = AmazonSource()
    results = s.search("tv")
    assert isinstance(results, list)


def test_reddit_initializes():
    s = RedditSource()
    assert s is not None


@patch("requests.get")
def test_reddit_search_returns_list(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "data": {"children": [{"data": {"title": "Recommend Samsung S95H OLED", "url": "https://reddit.com/r/tv"}}]}
    }
    s = RedditSource()
    results = s.search("tv")
    assert isinstance(results, list)


def test_google_trends_initializes():
    s = GoogleTrendsSource()
    assert s is not None


@patch("abvorn.trends.recon.providers.TrendReq")
def test_google_trends_search_returns_list(MockTrendReq):
    mock_instance = MagicMock()
    mock_df = MagicMock()
    mock_df.head.return_value.to_dict.return_value = [{"query": "OLED TV deals"}]
    mock_instance.related_queries.return_value = {"tv": {"rising": mock_df}}
    MockTrendReq.return_value = mock_instance
    s = GoogleTrendsSource()
    results = s.search("tv")
    assert isinstance(results, list)


@patch("abvorn.trends.recon.providers.DDGS")
def test_unknown_category_returns_empty(MockDDGS):
    mock_instance = MagicMock()
    mock_instance.text.return_value = []
    MockDDGS.return_value = mock_instance
    s = DuckDuckGoSource()
    s._ddgs = mock_instance
    results = s.search("zzz_not_a_real_niche")
    assert isinstance(results, list)


# --- Scanner integration tests ---

from abvorn.trends.scanner import TrendScanner


def test_scanner_initializes():
    scanner = TrendScanner()
    assert scanner is not None
    assert len(scanner._recon_providers) == 4
    assert scanner.min_score == 40


@patch("abvorn.trends.recon.providers.DDGS")
@patch("requests.get")
@patch("abvorn.trends.recon.providers.TrendReq")
def test_scanner_scan_returns_list(MockTrendReq, mock_get, MockDDGS):
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = [
        {"title": "Samsung S95H OLED TV", "body": "Best TV 2026", "href": ""},
    ]
    MockDDGS.return_value = mock_ddgs
    mock_get.return_value.status_code = 200
    mock_get.return_value.text = '<div>nothing</div>'
    mock_get.return_value.json.return_value = {"data": {"children": []}}
    mock_trend = MagicMock()
    mock_df = MagicMock()
    mock_df.head.return_value.to_dict.return_value = []
    mock_trend.related_queries.return_value = {"tv": {"rising": mock_df}}
    MockTrendReq.return_value = mock_trend
    scanner = TrendScanner()
    scanner._recon_providers = [
        DuckDuckGoSource(), AmazonSource(), RedditSource(), GoogleTrendsSource()
    ]
    scanner._recon_providers[0]._ddgs = mock_ddgs
    results = scanner.scan(["tv"])
    assert isinstance(results, list)


@patch("abvorn.trends.recon.providers.DDGS")
@patch("requests.get")
@patch("abvorn.trends.recon.providers.TrendReq")
def test_scanner_aggregates_multiple_sources(MockTrendReq, mock_get, MockDDGS):
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = [
        {"title": "Samsung S95H OLED TV", "body": "Best TV 2026", "href": ""},
    ]
    MockDDGS.return_value = mock_ddgs
    mock_get.return_value.status_code = 200
    mock_get.return_value.text = '<div class="p13n-sc-uncoverable-faceout"><div class="_cDEzb_p13n-sc-css-line-clamp-3_g3dy1">Samsung S95H</div></div>'
    mock_get.return_value.json.return_value = {"data": {"children": []}}
    mock_trend = MagicMock()
    mock_df = MagicMock()
    mock_df.head.return_value.to_dict.return_value = []
    mock_trend.related_queries.return_value = {"tv": {"rising": mock_df}}
    MockTrendReq.return_value = mock_trend
    scanner = TrendScanner()
    scanner._recon_providers = [
        DuckDuckGoSource(), AmazonSource(), RedditSource(), GoogleTrendsSource()
    ]
    scanner._recon_providers[0]._ddgs = mock_ddgs
    scanner.clear_cache()
    results = scanner.scan(["tv"])
    if results:
        r = results[0]
        assert "product_name" in r
        assert "score" in r
        assert "sources" in r


@patch("abvorn.trends.recon.providers.DDGS")
@patch("requests.get")
@patch("abvorn.trends.recon.providers.TrendReq")
def test_scanner_deduplicates(MockTrendReq, mock_get, MockDDGS):
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = [
        {"title": "Samsung S95H OLED TV", "body": "Best TV 2026", "href": ""},
    ]
    MockDDGS.return_value = mock_ddgs
    mock_get.return_value.status_code = 200
    mock_get.return_value.text = '<div>nothing</div>'
    mock_get.return_value.json.return_value = {"data": {"children": []}}
    mock_trend = MagicMock()
    mock_df = MagicMock()
    mock_df.head.return_value.to_dict.return_value = []
    mock_trend.related_queries.return_value = {"tv": {"rising": mock_df}}
    MockTrendReq.return_value = mock_trend
    scanner = TrendScanner()
    scanner._recon_providers = [
        DuckDuckGoSource(), AmazonSource(), RedditSource(), GoogleTrendsSource()
    ]
    scanner._recon_providers[0]._ddgs = mock_ddgs
    scanner.clear_cache()
    results = scanner.scan(["tv"])
    names = [r["product_name"].lower() for r in results]
    assert len(names) == len(set(names))