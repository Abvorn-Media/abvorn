import pytest, tempfile
from pathlib import Path
from abvorn.orchestrator.health import HealthMonitor


def test_health_check_passes():
    """Should pass health check when everything is normal."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "state.db"
        monitor = HealthMonitor(state_db=str(db))
        status = monitor.check()
        assert status["healthy"] == True
        monitor.state.close()


def test_health_logs_cycle():
    """Should log a cycle completion and track success rate."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "state.db"
        monitor = HealthMonitor(state_db=str(db))
        monitor.log_cycle("wireless headphones", success=True, duration_s=120)
        stats = monitor.get_stats()
        assert stats["total_cycles"] == 1
        assert stats["success_rate"] == 1.0
        monitor.state.close()


def test_health_tracks_failures():
    """Should track failure rate over time."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "state.db"
        monitor = HealthMonitor(state_db=str(db))
        monitor.log_cycle("niche1", success=True, duration_s=60)
        monitor.log_cycle("niche2", success=False, duration_s=30)
        stats = monitor.get_stats()
        assert stats["total_cycles"] == 2
        assert stats["success_rate"] == 0.5
        monitor.state.close()