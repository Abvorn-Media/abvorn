import shutil
import tempfile
from pathlib import Path

import pytest

from abvorn.domination.orchestrator import DominationOrchestrator


@pytest.fixture
def learn_db(tmp_path):
    yield str(tmp_path / "learn.db")
    for p in sorted(tmp_path.glob("*"), reverse=True):
        try:
            p.unlink()
        except OSError:
            pass


class _FakeIntel:
    def __init__(self, entries):
        self._entries = entries

    def parse(self):
        return self._entries


class _FakePublisher:
    """Publish nothing; the test only cares about target selection."""

    def publish_all(self, publish_targets, niche, media_paths=None):
        return [{"status": "posted", "platform": p} for p in publish_targets]


def _make_orchestrator(entries, db_path):
    orch = DominationOrchestrator()
    orch.content_intel = _FakeIntel(entries)
    orch.publisher = _FakePublisher()
    orch.pexels = _NoopAssets()
    orch.cinematic = _NoopCinematic()
    orch.audio = _NoopAudio()
    orch.learner = _NoopLearner(db_path)
    return orch


class _NoopAssets:
    def asset_for_niche(self, niche, count=1):
        return []


class _NoopCinematic:
    def apply_brand_overlay(self, *a, **k):
        return None


class _NoopAudio:
    def generate_voiceover_script(self, *a, **k):
        pass

    def count_assets(self):
        return 0


class _NoopLearner:
    def __init__(self, db_path):
        from abvorn.domination.self_learning_engine import SelfLearningEngine
        self._sle = SelfLearningEngine(db_path=db_path)

    def posted_urls(self):
        return self._sle.posted_urls()

    def record_hook_test(self, *a, **k):
        return 1

    def record_post_performance(self, url, niche, platform, **k):
        self._sle.record_post_performance(url=url, niche=niche, platform=platform)

    def record_posting_time(self, *a, **k):
        pass


def _entries():
    return [
        {
            "title": "Top Laptops",
            "niche": "laptops",
            "url": "https://abvorn.com/reviews/laptops/",
            "virality_score": 90,
            "sentiment": "positive",
        },
        {
            "title": "Top Mice",
            "niche": "mice",
            "url": "https://abvorn.com/reviews/mice/",
            "virality_score": 80,
            "sentiment": "positive",
        },
        {
            "title": "Top Keyboards",
            "niche": "keyboards",
            "url": "https://abvorn.com/reviews/keyboards/",
            "virality_score": 70,
            "sentiment": "positive",
        },
    ]


def test_cycle_picks_top_unposted_entry_on_second_run(learn_db):
    orch = _make_orchestrator(_entries(), learn_db)
    first = orch.run_cycle()
    assert first["title"] == "Top Laptops"
    second = orch.run_cycle()
    assert second["title"] == "Top Mice"
    third = orch.run_cycle()
    assert third["title"] == "Top Keyboards"


def test_cycle_with_niche_skips_posted_entries_in_niche(learn_db):
    entries = _entries()
    orch = _make_orchestrator(entries, learn_db)
    first = orch.run_cycle(niche="laptops")
    assert first["title"] == "Top Laptops"
    # second run in same niche: laptops already posted -> fall back to any laptops entry
    second = orch.run_cycle(niche="laptops")
    assert second["title"] == "Top Laptops"


def test_cycle_all_posted_falls_back_to_first_entry(learn_db):
    orch = _make_orchestrator(_entries(), learn_db)
    orch.run_cycle()
    orch.run_cycle()
    orch.run_cycle()
    # all three posted -> next run falls back to entries[0]
    fourth = orch.run_cycle()
    assert fourth["title"] == "Top Laptops"