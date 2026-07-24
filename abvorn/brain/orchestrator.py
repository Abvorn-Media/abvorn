"""Full brain refresh orchestration: scan → extract → index → retrieve."""

import json, logging
from pathlib import Path
from .scanner import scan_brain, extract_text
from .indexer import KnowledgeIndex
from .retriever import KnowledgeRetriever

logger = logging.getLogger("abvorn.brain")

BRAIN_DB_PATH = Path.home() / ".abvorn" / "brain_index.db"

def refresh_brain() -> dict:
    """Full brain refresh: scan → extract → index → return summary."""
    categories = scan_brain()
    if not categories:
        return {"status": "no_brain", "documents": 0}

    index = KnowledgeIndex(str(BRAIN_DB_PATH))
    indexed = 0

    for domain, files in categories.items():
        for f in files:
            text = extract_text(f["path"])
            if text:
                index.ingest_pdf(f["path"], domain, text, f.get("hash", ""))
                indexed += 1

    retriever = KnowledgeRetriever(index)
    summary = retriever.summarize_knowledge_base()
    logger.info(f"Brain refresh complete: {indexed} documents indexed")
    return {"status": "ok", "indexed": indexed, "summary": summary}

def get_brain_retriever() -> KnowledgeRetriever:
    """Get or create a retriever for the current brain index."""
    if not BRAIN_DB_PATH.exists():
        refresh_brain()
    index = KnowledgeIndex(str(BRAIN_DB_PATH))
    return KnowledgeRetriever(index)
