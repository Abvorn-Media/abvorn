"""Regression tests for A2 (real vs estimated revenue) and A3 (durable cost log)."""
import os
import tempfile
from pathlib import Path

from abvorn.core.models import ModelCostTracker
from abvorn.core.unified_database import UnifiedDatabase
from src import economic_surplus
from src.economic_surplus import EconomicSurplusTracker, _main


def _isolated_db(tmp_path) -> None:
    os.environ["ABVORN_DB_PATH"] = str(tmp_path / "verify.db")


def test_model_cost_tracker_persists_durable_cost(tmp_path):
    _isolated_db(tmp_path)
    tracker = ModelCostTracker()
    tracker.record_call("anthropic", "claude-sonnet", "draft", 10000, 500, True)
    tracker.record_call("openai", "gpt-4o", "brain", 5000, 200, True)
    tracker.record_call("moonshot", "kimi", "research", 2000, 100, False)
    stats = tracker.get_stats()
    assert stats["total_calls"] == 3
    assert stats["successful"] == 2
    assert stats["failed"] == 1
    assert stats["durable_entries"] == 3
    assert stats["durable_cost_usd"] > 0
    assert stats["estimated_cost_usd"] == round(stats["durable_cost_usd"], 4)


def test_cost_log_table_records_provider_rates(tmp_path):
    _isolated_db(tmp_path)
    db = UnifiedDatabase()
    db.log_cost("anthropic", "claude-sonnet", tokens_in=1000, tokens_out=0,
                rate_per_1k_in=0.003, rate_per_1k_out=0.015, cost=0.003,
                source="draft")
    summary = db.get_cost_summary()
    assert summary["entries"] == 1
    assert abs(summary["total_cost"] - 0.003) < 1e-9


def test_real_vs_estimated_revenue_distinguished(tmp_path):
    tracker = EconomicSurplusTracker(data_dir=str(tmp_path / "surplus"))
    tracker.record_revenue(12.50, "affiliate:payout-1", niche="audio", costs=2.0)
    tracker.record_article("a1", "audio", 5.0)  # default = estimated
    assert abs(tracker.real_revenue_total() - 12.50) < 1e-6
    assert abs(tracker.estimated_revenue_total() - 5.0) < 1e-6
    report = tracker.measure()
    breakdown = report["revenue_breakdown"]
    assert abs(breakdown["real"] - 12.50) < 1e-6
    assert abs(breakdown["estimated"] - 5.0) < 1e-6
    assert abs(breakdown["total"] - 17.50) < 1e-6


def test_import_real_revenue_json(tmp_path):
    tracker = EconomicSurplusTracker(data_dir=str(tmp_path / "surplus2"))
    src = Path(tmp_path) / "revenue.json"
    src.write_text('[{"source": "aff:a", "revenue": 3.25, "costs": 0.5},'
                   ' {"source": "aff:b", "revenue": 9, "costs": 1.0}]', encoding="utf-8")
    count = tracker.import_real_revenue_json(str(src))
    assert count == 2
    assert abs(tracker.real_revenue_total() - 12.25) < 1e-6


def test_cli_import_json(tmp_path, monkeypatch, capsys):
    src = Path(tmp_path) / "payout.json"
    src.write_text('[{"source": "aff:amazon-1", "revenue": 5.20, "costs": 0.0,'
                   ' "niche": "audio"}]', encoding="utf-8")

    def _fake_factory():
        return EconomicSurplusTracker(data_dir=str(tmp_path / "surplus_cli"))

    monkeypatch.setattr(economic_surplus, "create_economic_surplus_tracker", _fake_factory)
    rc = _main(["import-json", str(src)])
    out = capsys.readouterr().out
    assert rc == 0
    assert '"imported": 1' in out
    assert '"real": 5.2' in out


def test_cli_summary(tmp_path, monkeypatch, capsys):
    def _fake_factory():
        tracker = EconomicSurplusTracker(data_dir=str(tmp_path / "surplus_cli2"))
        tracker.record_revenue(9.99, "aff:payout-x", niche="gaming")
        return tracker

    monkeypatch.setattr(economic_surplus, "create_economic_surplus_tracker", _fake_factory)
    rc = _main(["summary"])
    out = capsys.readouterr().out
    assert rc == 0
    assert '"real": 9.99' in out
