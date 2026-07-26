"""BackupManager — safe state DB snapshots with rotation and restore."""

import shutil
import json
import logging
import os
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("abvorn.monitor.backup")

MAX_BACKUPS = 10
BACKUP_DIR_NAME = "backups"


class BackupManager:
    """Creates and manages state DB snapshots for safe rollback."""

    def __init__(self, state_path: Path = None):
        self._state_path = state_path or Path.home() / ".abvorn" / "state.db"
        self._backup_dir = self._state_path.parent / BACKUP_DIR_NAME
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def create(self, label: str = "") -> str:
        """Snapshot the state DB. Returns backup name."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)[:30]
        name = f"{timestamp}_{safe_label}" if safe_label else timestamp
        dest = self._backup_dir / f"{name}.db"
        shutil.copy2(str(self._state_path), str(dest))
        self._prune()
        logger.info(f"Backup created: {name}")
        return name

    def list_backups(self) -> list[dict]:
        """Return sorted list of backups with timestamps."""
        backups = []
        for f in sorted(self._backup_dir.glob("*.db"), reverse=True):
            stat = f.stat()
            backups.append({
                "name": f.stem,
                "size_kb": stat.st_size // 1024,
                "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        return backups

    def restore(self, name: str) -> bool:
        """Restore state DB from a backup. Matches by suffix. Returns True on success."""
        # Try exact match first, then suffix match
        src = self._backup_dir / f"{name}.db"
        if not src.exists():
            backups = list(self._backup_dir.glob("*.db"))
            matches = [b for b in backups if b.stem.endswith(name)]
            if not matches:
                logger.error(f"Backup not found: {name}")
                return False
            src = matches[0]
        self.create("pre_restore")
        shutil.copy2(str(src), str(self._state_path))
        logger.info(f"Restored from backup: {src.stem}")
        return True

    def format_list(self) -> str:
        """Format backup list for Telegram display."""
        backups = self.list_backups()
        if not backups:
            return "<b>Backups</b>\nNo backups found."
        lines = ["<b>Backups</b>"]
        for b in backups[:10]:
            name_short = b['name'][20:] if len(b['name']) > 20 else b['name']
            lines.append(f"  {name_short}  ({b['size_kb']}KB, {b['created'][:16]})")
        return "\n".join(lines)

    def _prune(self):
        """Remove oldest backups beyond MAX_BACKUPS."""
        backups = sorted(self._backup_dir.glob("*.db"), key=lambda f: f.stat().st_mtime)
        limit = getattr(self, 'MAX_BACKUPS', MAX_BACKUPS)
        while len(backups) > limit:
            backups[0].unlink()
            backups.pop(0)
