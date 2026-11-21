"""Tests for the GSC ingestor's status handling and category demand rollup."""

import json

import pytest

from abvorn.core.gsc_client import GSCClient
from abvorn.core.gsc_ingestor import GSCIngestor, category_evidence


class _FakeClient:
    def __init__(self, rows):
        self._rows = rows
        self.enabled = True
        self.last_dims = None

    def fetch_performance(self, days, dimensions=None):
        self.last_dims = dimensions
        return self._rows

    def fetch_top_performing(self, days):
        return []

    def fetch_growth_opportunities(self, days):
        return []


class _FakeClientDisabled(_FakeClient):
    def __init__(self):
        super().__init__([])
        self.enabled = False


def test_empty_window_reports_no_data_yet_not_failed(monkeypatch, tmp_path):
    ing = GSCIngestor.__new__(GSCIngestor)
    ing.client = _FakeClient([])
    ing.db = None
    ing.memory = None
    monkeypatch.chdir(tmp_path)
    result = ing.ingest_performance(days=30)
    assert result["status"] == "no_data_yet"
    assert "30" in result["error"]


def test_disabled_client_is_a_real_failure(monkeypatch, tmp_path):
    ing = GSCIngestor.__new__(GSCIngestor)
    ing.client = _FakeClientDisabled()
    ing.db = None
    ing.memory = None
    monkeypatch.chdir(tmp_path)
    result = ing.ingest_performance(days=30)
    assert result["status"] == "failed"


def test_data_window_reports_success(monkeypatch, tmp_path, capsys):
    rows = [{"clicks": 2, "impressions": 50, "ctr": 0.04, "position": 3.2}]
    ing = GSCIngestor.__new__(GSCIngestor)
    ing.client = _FakeClient(rows)
    ing.db = None
    ing.memory = None
    ing._store_summary = lambda rows, days: None
    ing._ingest_to_graphify = lambda data, data_type: None
    ing._generate_insights = lambda top, opp: []
    ing._write_to_journal = lambda insights: None
    ing._log_ingestion = lambda days, rows, top, opp: None
    monkeypatch.chdir(tmp_path)
    result = ing.ingest_performance(days=30)
    assert result["status"] == "success"
    assert result["rows_processed"] == 1
    assert ing.client.last_dims == []


def _write_gsc_file(tmp_path, filename, subtype, items):
    payload = {"type": "gsc_insight", "subtype": subtype, "items": items}
    (tmp_path / filename).write_text(json.dumps(payload), encoding="utf-8")


def test_growth_opportunity_rows_carry_url(monkeypatch):
    """Growth rows expose url (derived from page) for the demand rollup."""
    rows = [{
        "keys": ["best webcam 2026", "https://abvorn.com/reviews/webcams/best.html"],
        "clicks": 1, "impressions": 500, "ctr": 0.001, "position": 10,
    }]
    client = GSCClient.__new__(GSCClient)
    monkeypatch.setattr(client, "fetch_performance", lambda *a, **k: rows)

    result = client.fetch_growth_opportunities(30)

    assert result[0]["page"] == "https://abvorn.com/reviews/webcams/best.html"
    assert result[0]["url"] == result[0]["page"]


@pytest.mark.parametrize("key", ["url", "page"])
def test_growth_only_file_feeds_category_evidence(tmp_path, key):
    """Demand from growth rows alone reaches the category evidence gate."""
    _write_gsc_file(tmp_path, "gsc_growth_opportunity.json", "growth_opportunity", [{
        key: "https://abvorn.com/reviews/webcams/best-webcam-2026.html",
        "query": "best webcam", "impressions": 600, "clicks": 3,
    }])

    assert category_evidence(str(tmp_path)) == {
        "webcams": {"impressions": 600, "clicks": 3},
    }


def test_growth_queries_for_one_url_count_once(tmp_path):
    """One page under many queries contributes its max demand only once."""
    url = "https://abvorn.com/reviews/webcams/best-webcam-2026.html"
    _write_gsc_file(tmp_path, "gsc_growth_opportunity.json", "growth_opportunity", [
        {
            "url": url, "query": f"webcam query {i}",
            "impressions": 900 + i, "clicks": 4 + i,
        }
        for i in range(20)
    ])

    assert category_evidence(str(tmp_path)) == {
        "webcams": {"impressions": 919, "clicks": 23},
    }


def test_same_url_in_both_files_counts_max_not_sum(tmp_path):
    """A URL present in both files uses max(impressions), max(clicks)."""
    url = "https://abvorn.com/reviews/webcams/best-webcam-2026.html"
    _write_gsc_file(tmp_path, "gsc_top_performing.json", "top_performing", [
        {"url": url, "impressions": 500, "clicks": 10},
    ])
    _write_gsc_file(tmp_path, "gsc_growth_opportunity.json", "growth_opportunity", [
        {"url": url, "query": "best webcam", "impressions": 900, "clicks": 3},
    ])

    assert category_evidence(str(tmp_path)) == {
        "webcams": {"impressions": 900, "clicks": 10},
    }


def test_two_urls_in_segment_sum_per_url_maxima(tmp_path):
    """Distinct URLs in one segment sum their per-URL maxima across files."""
    first = "https://abvorn.com/reviews/webcams/first.html"
    second = "https://abvorn.com/reviews/webcams/second.html"
    _write_gsc_file(tmp_path, "gsc_top_performing.json", "top_performing", [
        {"url": first, "impressions": 500, "clicks": 2},
        {"url": first, "impressions": 300, "clicks": 9},
    ])
    _write_gsc_file(tmp_path, "gsc_growth_opportunity.json", "growth_opportunity", [
        {"url": first, "query": "q1", "impressions": 400, "clicks": 1},
        {"url": second, "query": "q2", "impressions": 700, "clicks": 4},
    ])

    assert category_evidence(str(tmp_path)) == {
        "webcams": {"impressions": 1200, "clicks": 13},
    }


def test_missing_growth_file_keeps_top_only_behavior(tmp_path):
    """With no growth file the existing top-only demand is unchanged."""
    _write_gsc_file(tmp_path, "gsc_top_performing.json", "top_performing", [
        {"url": "https://abvorn.com/reviews/tv/first.html", "impressions": 800, "clicks": 5},
        {"url": "https://abvorn.com/reviews/webcams/second.html", "impressions": 400, "clicks": 2},
    ])

    assert category_evidence(str(tmp_path)) == {
        "tv": {"impressions": 800, "clicks": 5},
        "webcams": {"impressions": 400, "clicks": 2},
    }


@pytest.mark.parametrize(
    "bad_file,good_file,good_subtype",
    [
        ("gsc_top_performing.json", "gsc_growth_opportunity.json", "growth_opportunity"),
        ("gsc_growth_opportunity.json", "gsc_top_performing.json", "top_performing"),
    ],
)
def test_malformed_gsc_file_is_ignored(tmp_path, bad_file, good_file, good_subtype):
    """Malformed JSON in one file cannot raise or erase the other file's demand."""
    _write_gsc_file(tmp_path, good_file, good_subtype, [{
        "url": "https://abvorn.com/reviews/webcams/best-webcam-2026.html",
        "impressions": 600, "clicks": 3,
    }])
    (tmp_path / bad_file).write_text("{not json", encoding="utf-8")

    assert category_evidence(str(tmp_path)) == {
        "webcams": {"impressions": 600, "clicks": 3},
    }