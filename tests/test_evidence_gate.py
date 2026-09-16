"""Evidence gate + quality score for the autonomous publish path.

The daemon must not mint a page from a demand-less opportunity, and the
quality score it records must reflect real evidence instead of a hardcoded 7.0.
"""
import json

import pytest

from abvorn.daemon import quality_from_opportunity, satisfies_evidence


@pytest.fixture
def empty_data(tmp_path):
    (tmp_path / "gsc_top_performing.json").write_text(
        json.dumps({"type": "gsc_insight", "subtype": "top_performing", "items": []}),
        encoding="utf-8",
    )
    return str(tmp_path)


def _write_gsc(tmp_path, items):
    payload = {"type": "gsc_insight", "subtype": "top_performing", "items": items}
    (tmp_path / "gsc_top_performing.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return str(tmp_path)


def test_satisfies_evidence_manual_deploy_always_passes(empty_data):
    opp = {"score": 1.0, "category": "webcams", "search_volume": 0, "buying_intent": 0.5}
    assert satisfies_evidence(opp, min_score=0.5, data_dir=empty_data)


def test_satisfies_evidence_weak_trend_blocked(empty_data):
    opp = {"score": 0.4, "category": "webcams"}
    assert not satisfies_evidence(opp, min_score=0.5, data_dir=empty_data)


def test_satisfies_evidence_matches_high_bar(empty_data):
    opp = {"score": 0.7, "category": "webcams"}
    assert satisfies_evidence(opp, min_score=0.6, data_dir=empty_data)


def test_satisfies_evidence_gsc_demand_rescues(tmp_path):
    data_dir = _write_gsc(tmp_path, [{
        "url": "https://abvorn.com/reviews/webcams/best-webcam-2026.html",
        "clicks": 8, "impressions": 1200, "ctr": 0.006, "position": 12,
    }])
    opp = {"score": 0.3, "category": "webcams"}
    assert satisfies_evidence(opp, min_score=0.5, data_dir=data_dir)


def test_satisfies_evidence_unrelated_category_not_rescued(tmp_path):
    data_dir = _write_gsc(tmp_path, [{
        "url": "https://abvorn.com/reviews/tv/best-tv-2026.html",
        "clicks": 8, "impressions": 1200, "ctr": 0.006, "position": 12,
    }])
    opp = {"score": 0.3, "category": "webcams"}
    assert not satisfies_evidence(opp, min_score=0.5, data_dir=data_dir)


def test_quality_no_evidence_is_benchmark(empty_data):
    assert quality_from_opportunity({"score": 0.5, "category": "webcams"}, data_dir=empty_data) == 7.0


def test_quality_strong_trend_scores_higher(empty_data):
    assert quality_from_opportunity({"score": 1.0, "category": "webcams"}, data_dir=empty_data) == 10.0
    high = quality_from_opportunity({"score": 0.9, "category": "webcams"}, data_dir=empty_data)
    weak = quality_from_opportunity({"score": 0.4, "category": "webcams"}, data_dir=empty_data)
    assert high > weak


def test_quality_gsc_demand_boosts(tmp_path):
    data_dir = _write_gsc(tmp_path, [{
        "url": "https://abvorn.com/reviews/tv/best-tv-2026.html",
        "clicks": 5, "impressions": 800, "ctr": 0.006, "position": 15,
    }])
    boosted = quality_from_opportunity({"score": 0.4, "category": "tv"}, data_dir=data_dir)
    plain = quality_from_opportunity({"score": 0.4, "category": "tv"}, data_dir=str(tmp_path / "empty"))
    assert boosted > plain


def test_satisfies_evidence_copes_with_missing_data(empty_data):
    assert not satisfies_evidence({}, min_score=0.5, data_dir=empty_data)