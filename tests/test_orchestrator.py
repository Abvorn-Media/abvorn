import pytest, tempfile
from pathlib import Path
from abvorn.orchestrator.scheduler import Scheduler


def test_scheduler_queue():
    """Should return the highest-priority item from queue."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "state.db"
        sched = Scheduler(state_db=str(db))
        sched.state.add_opportunity("test niche", score=0.9, search_volume=5000)
        sched.state.add_opportunity("low niche", score=0.2, search_volume=100)
        next_item = sched.get_next_opportunity()
        assert next_item is not None
        assert next_item["niche"] == "test niche"
        sched.state.close()


def test_scheduler_empty_queue():
    """Should return None when queue is empty."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "state.db"
        sched = Scheduler(state_db=str(db))
        assert sched.get_next_opportunity() is None
        sched.state.close()


def test_mark_complete():
    """Should mark an opportunity as completed."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "state.db"
        sched = Scheduler(state_db=str(db))
        sched.state.add_opportunity("test", 0.9)
        opp = sched.get_next_opportunity()
        assert opp is not None
        sched.mark_complete(opp["id"])
        assert sched.get_next_opportunity() is None
        sched.state.close()