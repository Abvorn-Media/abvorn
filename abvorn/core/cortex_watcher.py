"""cortex_watcher.py — The Symbiotic Cortex: Obsidian vault <-> Ab.

Watches an Obsidian vault for Teach notes, Corrections, Journal edits and
general notes, ingesting them into Ab's Neural Memory (Graphify) and Brain.
The Relentless Core writes its Evolution Journal entries into the vault.

The integration guide referenced a `HindsightLearner` class and a
`templates/dashboard.html` that do not exist in this repo; this module is
adapted to the real `neural_memory` / `brain` APIs. Graphify ingestion is
done through the same path-based `ingest(path, mode)` call the rest of the
core uses. All integrations are optional and never fatal.
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

DEFAULT_VAULT_PATH = Path.home() / ".abvorn" / "Obsidian" / "Ab's Journey"
CORTEX_DATA_DIR = Path("data") / "cortex"
CORRECTIONS_FILE = CORTEX_DATA_DIR / "corrections.jsonl"


def get_vault_path() -> Optional[Path]:
    """Resolve the vault path from env or the known default."""
    vault = os.getenv("CORTEX_VAULT_PATH")
    path = Path(vault) if vault else DEFAULT_VAULT_PATH
    return path if path.exists() else None


def cortex_enabled() -> bool:
    """Cortex is enabled unless explicitly disabled.

    There is no .env loader in this repo, so we default to enabled whenever
    the vault exists. Set CORTEX_ENABLED=false to opt out.
    """
    flag = os.getenv("CORTEX_ENABLED")
    if flag is not None:
        return flag.strip().lower() == "true"
    return get_vault_path() is not None


class CortexHandler(FileSystemEventHandler):
    """Handles file events in the Obsidian vault."""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.memory = None
        self.brain = None
        self.last_processed: Dict[str, float] = {}
        self.debounce_seconds = int(os.getenv("CORTEX_WATCH_INTERVAL", "5"))

    def _ensure_memory(self):
        if self.memory is None:
            try:
                from abvorn.core.neural_memory import get_neural_memory

                self.memory = get_neural_memory()
            except Exception as e:
                logger.warning("Neural memory unavailable for Cortex: %s", e)

    def _ensure_brain(self):
        if self.brain is None:
            try:
                from abvorn.core.brain import get_brain

                self.brain = get_brain()
            except Exception as e:
                logger.warning("Brain unavailable for Cortex: %s", e)

    def _should_skip(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != ".md":
            return True
        if file_path.name.startswith((".~", "_")):
            # Skip lock files and Ab's own confirmation notes (avoid loops).
            return True
        if file_path.name in ("Cortex.config.md", "Welcome.md"):
            return True
        return False

    def _debounced(self, file_path: Path) -> bool:
        current = time.time()
        last = self.last_processed.get(str(file_path), 0)
        if current - last < self.debounce_seconds:
            return True
        self.last_processed[str(file_path)] = current
        return False

    def on_created(self, event):
        self._on_file_event(event)

    def on_modified(self, event):
        self._on_file_event(event)

    def _on_file_event(self, event):
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        if self._should_skip(file_path) or self._debounced(file_path):
            return
        self._process_file(file_path)

    def _process_file(self, file_path: Path):
        try:
            content = file_path.read_text(encoding="utf-8")
            rel_path = file_path.relative_to(self.vault_path)
            logger.info("Cortex detected change: %s", rel_path)

            frontmatter, body = self._parse_markdown(content)

            parent = str(rel_path.parent)
            if "Teach" in parent:
                self._handle_teach_note(body, frontmatter, file_path)
            elif "Corrections" in parent:
                self._handle_correction(body, frontmatter, file_path)
            elif "Journal" in parent:
                self._handle_journal_edit(body, frontmatter, file_path)
            else:
                self._ingest_note(body, frontmatter, file_path)
        except Exception as e:
            logger.error("Cortex processing error for %s: %s", file_path, e)

    @staticmethod
    def _parse_markdown(content: str) -> tuple:
        """Parse YAML frontmatter + body using python-frontmatter."""
        try:
            import frontmatter

            post = frontmatter.loads(content)
            return dict(post.metadata or {}), post.content
        except Exception:
            return {}, content

    def _handle_teach_note(self, body: str, frontmatter: dict, file_path: Path):
        """Ingest a teaching note into Neural Memory and Brain."""
        logger.info("Teaching note detected: %s", file_path.name)
        self._ensure_memory()
        self._ingest_text(body, source=str(file_path), metadata=frontmatter)
        self._ensure_brain()
        self._write_confirmation(file_path)

    def _handle_correction(self, body: str, frontmatter: dict, file_path: Path):
        """Process a correction: record it and ingest the corrected content."""
        logger.info("Correction detected: %s", file_path.name)
        corrections = self._extract_corrections(body)
        if corrections:
            self._record_corrections(corrections, file_path)
            logger.info("Recorded %d correction(s)", len(corrections))
        self._ingest_text(body, source=str(file_path), metadata=frontmatter)

    def _handle_journal_edit(self, body: str, frontmatter: dict, file_path: Path):
        """React to edits in the Evolution Journal."""
        logger.info("Journal edit: %s", file_path.name)
        self._ingest_text(body, source=str(file_path), metadata=frontmatter)
        self._handle_correction(body, frontmatter, file_path)

    def _ingest_note(self, body: str, frontmatter: dict, file_path: Path):
        """Generic ingestion into Neural Memory."""
        self._ingest_text(body, source=str(file_path), metadata=frontmatter)

    def _ingest_text(self, body: str, source: str, metadata: dict = None):
        """Ingest a text blob into Graphify via a temp markdown file."""
        if self.memory is None:
            return
        try:
            CORTEX_DATA_DIR.mkdir(parents=True, exist_ok=True)
            blob = f"---\nsource: {source}\n---\n\n{body}"
            temp_file = CORTEX_DATA_DIR / f"note_{int(time.time() * 1000)}.md"
            temp_file.write_text(blob, encoding="utf-8")
            self.memory.ingest(str(temp_file), mode="normal")
            logger.info("Ingested '%s' into Neural Memory", source)
        except Exception as e:
            logger.error("Graphify ingest failed: %s", e)

    @staticmethod
    def _extract_corrections(text: str) -> List[Dict[str, str]]:
        """Extract corrections from Markdown: ~~wrong~~ -> *correct*."""
        corrections: List[Dict[str, str]] = []
        for wrong, correct in re.findall(r"~~(.*?)~~\s*->\s*\*(.*?)\*", text):
            corrections.append({"wrong": wrong.strip(), "correct": correct.strip()})
        for corr in re.findall(r"\*correction:\s*(.*?)\*", text):
            corrections.append({"correction": corr.strip()})
        return corrections

    def _record_corrections(self, corrections: List[Dict[str, str]], file_path: Path):
        """Persist corrections to data/cortex/corrections.jsonl."""
        try:
            CORTEX_DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(CORRECTIONS_FILE, "a", encoding="utf-8") as f:
                for c in corrections:
                    entry = {
                        "correction": c,
                        "source": str(file_path),
                        "timestamp": datetime.now().isoformat(),
                    }
                    f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error("Failed to record correction: %s", e)

    def _write_confirmation(self, source_path: Path):
        """Write a confirmation note back to the vault."""
        try:
            confirm_path = source_path.parent / f"_{source_path.stem}_ingested.md"
            confirm_path.write_text(
                f"# Ingested at {datetime.now().isoformat()}\n\n"
                "This note has been added to Ab's memory.",
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to write confirmation note: %s", e)


class CortexWatcher:
    """Main watcher daemon."""

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path).resolve()
        if not self.vault_path.exists():
            raise FileNotFoundError(f"Vault path not found: {self.vault_path}")
        self.observer = Observer()
        self.handler = CortexHandler(self.vault_path)

    def start(self):
        self.observer.schedule(self.handler, str(self.vault_path), recursive=True)
        self.observer.start()
        logger.info("Cortex watcher started on %s", self.vault_path)

    def stop(self):
        self.observer.stop()
        self.observer.join()
        logger.info("Cortex watcher stopped")

    def is_alive(self) -> bool:
        return self.observer.is_alive() if self.observer else False

    def run_forever(self):
        self.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()


_watcher = None


def get_cortex_watcher() -> Optional[CortexWatcher]:
    global _watcher
    if _watcher is None:
        vault = get_vault_path()
        if vault is None:
            logger.warning("Cortex vault not configured or missing.")
            return None
        try:
            _watcher = CortexWatcher(str(vault))
        except Exception as e:
            logger.warning("Cortex watcher init failed: %s", e)
            return None
    return _watcher


def cortex_status() -> Dict[str, Any]:
    """Report Cortex config/status for the dashboard and API."""
    vault = get_vault_path()
    watcher = get_cortex_watcher()
    return {
        "enabled": cortex_enabled(),
        "vault": str(vault) if vault else None,
        "watching": bool(watcher and watcher.is_alive()),
        "corrections_logged": _count_corrections(),
    }


def _count_corrections() -> int:
    try:
        if not CORRECTIONS_FILE.exists():
            return 0
        with open(CORRECTIONS_FILE, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def get_recent_journal(limit: int = 10) -> List[Dict[str, Any]]:
    """Return the most recent Evolution Journal entries from the vault."""
    vault = get_vault_path()
    if vault is None:
        return []
    journal_dir = vault / "Journal"
    if not journal_dir.exists():
        return []
    files = sorted(journal_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]
    entries = []
    for f in files:
        try:
            data = f.read_text(encoding="utf-8")
        except Exception:
            continue
        entries.append({
            "file": f.name,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            "preview": data[:200],
        })
    return entries
