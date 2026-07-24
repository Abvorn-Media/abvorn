import pytest, tempfile
from pathlib import Path
from abvorn.core.state import AbvornState


def test_kill_switch_default_off():
    """Kill switch should be False by default."""
    with tempfile.TemporaryDirectory() as tmp:
        state = AbvornState(Path(tmp) / "test.db")
        assert state.get_meta("kill_switch", False) is False
        state.close()


def test_kill_switch_toggle():
    """Should persist pause/resume state."""
    with tempfile.TemporaryDirectory() as tmp:
        state = AbvornState(Path(tmp) / "test.db")
        state.set_meta("kill_switch", True)
        assert state.get_meta("kill_switch", False) is True
        state.set_meta("kill_switch", False)
        assert state.get_meta("kill_switch", False) is False
        state.close()