"""Tests for the GSC ingestor's status handling (no-data window vs real failure)."""

import pytest

from abvorn.core.gsc_ingestor import GSCIngestor


class _FakeClient:
    def __init__(self, rows):
        self._rows = rows
        self.enabled = True

    def fetch_performance(self, days):
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