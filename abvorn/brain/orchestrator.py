"""Full brain refresh orchestration: scan → extract → index → retrieve."""

import json, logging
from pathlib import Path
from .scanner import scan_brain, extract_text
from .indexer import KnowledgeIndex
from .retriever import KnowledgeRetriever

logger = logging.getLogger("abvorn.brain")

BRAIN_DB_PATH = Path.home() / ".abvorn" / "brain_index.db"

def refresh_brain() -> dict:
    """Full brain refresh: scan → extract → index → return summary.

    Incremental: files already indexed (by path + hash) are skipped, so
    repeated runs only pick up new/changed documents.
    """
    categories = scan_brain()
    if not categories:
        return {"status": "no_brain", "documents": 0}

    index = KnowledgeIndex(str(BRAIN_DB_PATH))
    indexed = 0
    skipped = 0

    for domain, files in categories.items():
        for f in files:
            if _already_indexed(index, f):
                skipped += 1
                continue
            text = extract_text(f["path"])
            if text:
                index.ingest_pdf(f["path"], domain, text, f.get("hash", ""))
                indexed += 1

    retriever = KnowledgeRetriever(index)
    summary = retriever.summarize_knowledge_base()
    logger.info(f"Brain refresh complete: {indexed} new, {skipped} already indexed")
    return {"status": "ok", "indexed": indexed, "skipped": skipped, "summary": summary}


def _already_indexed(index: KnowledgeIndex, file_info: dict) -> bool:
    """True if the file path exists in the index and its hash matches."""
    path = file_info.get("path", "")
    file_hash = file_info.get("hash", "")
    if not path:
        return False
    with index._cursor() as c:
        c.execute("SELECT hash FROM documents WHERE path=?", (path,))
        row = c.fetchone()
    if not row:
        return False
    return bool(file_hash) and row[0] == file_hash

def get_brain_retriever() -> KnowledgeRetriever:
    """Get or create a retriever for the current brain index."""
    if not BRAIN_DB_PATH.exists():
        refresh_brain()
    index = KnowledgeIndex(str(BRAIN_DB_PATH))
    return KnowledgeRetriever(index)
