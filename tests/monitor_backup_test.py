"""Tests for BackupManager and EnvMode."""
from pathlib import Path
import tempfile, os
from abvorn.monitor.backup import BackupManager
from abvorn.monitor.env import EnvMode


def test_backup_creates_snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "state.db"
        state_path.write_text("test data")
        bm = BackupManager(state_path)
        name = bm.create("test_backup")
        assert name.endswith("_test_backup")
        assert (bm._backup_dir / f"{name}.db").exists()


def test_backup_list():
    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "state.db"
        state_path.write_text("test data")
        bm = BackupManager(state_path)
        bm.create("backup_a")
        bm.create("backup_b")
        backups = bm.list_backups()
        assert len(backups) == 2


def test_backup_restore():
    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "state.db"
        state_path.write_text("original")
        bm = BackupManager(state_path)
        bm.create("pre_change")
        state_path.write_text("modified")
        bm.restore("pre_change")
        assert state_path.read_text() == "original"


def test_backup_prune():
    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "state.db"
        state_path.write_text("data")
        bm = BackupManager(state_path)
        bm.MAX_BACKUPS = 2
        bm.create("b1")
        bm.create("b2")
        bm.create("b3")
        assert len(bm.list_backups()) <= 2


def test_env_defaults_to_development():
    env = EnvMode()
    assert env.is_development is True
    assert env.should_deploy is False
    assert env.should_post_social is False


def test_env_production(monkeypatch):
    monkeypatch.setenv("ABVORN_ENV", "production")
    env = EnvMode()
    assert env.is_production is True
    assert env.should_deploy is True
    assert env.should_post_social is True


def test_env_staging(monkeypatch):
    monkeypatch.setenv("ABVORN_ENV", "staging")
    env = EnvMode()
    assert env.is_staging is True
    assert env.should_deploy is True
    assert env.should_post_social is False
