"""Walks the brain directory, detects new/modified PDFs, extracts text."""

import hashlib, logging, json, os, re
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("abvorn.brain.scanner")

BRAIN_PATH = Path(os.environ.get("ABVORN_BRAIN_PATH", "")) if os.environ.get("ABVORN_BRAIN_PATH") else None
DEFAULT_PATHS = [
    BRAIN_PATH,
    Path("/content/drive/MyDrive/Notebook LM Brain"),
    Path.home() / ".abvorn" / "brain",
    Path(r"C:\Users\Jean Mare\Downloads\Notebook LM Brain-20260803T004108Z-1-001\Notebook LM Brain"),
]

def _find_brain() -> Path:
    """Return the first candidate path that contains at least one PDF (prefers real libraries over empty stubs)."""
    candidates = [p for p in DEFAULT_PATHS if p is not None and p.exists()]
    for p in candidates:
        try:
            if p.is_dir() and any(p.rglob("*.pdf")):
                return p
        except OSError:
            continue
    for p in candidates:
        if p.is_dir():
            return p
    local = Path.home() / ".abvorn" / "brain"
    local.mkdir(parents=True, exist_ok=True)
    return local

def scan_brain() -> dict:
    """Walk the brain directory, return categorized file listing."""
    brain = _find_brain()
    if not brain.exists():
        logger.warning(f"Brain directory not found: {brain}")
        return {}
    categories = {}
    for entry in brain.iterdir():
        if entry.is_dir():
            pdfs = list(entry.glob("*.pdf"))
            if pdfs:
                cat_name = entry.name.replace("_", " ").title()
                categories[cat_name] = []
                for pdf in pdfs:
                    mtime = datetime.fromtimestamp(pdf.stat().st_mtime)
                    h = hashlib.md5(pdf.read_bytes()[:4096]).hexdigest()
                    categories[cat_name].append({
                        "path": str(pdf),
                        "name": pdf.stem,
                        "size": pdf.stat().st_size,
                        "modified": mtime.isoformat(),
                        "hash": h,
                    })
    total = sum(len(v) for v in categories.values())
    logger.info(f"Brain scan: {len(categories)} categories, {total} documents")
    return categories

TEXT_LIMIT = 50000

def extract_text(pdf_path: str, limit: int = TEXT_LIMIT) -> str:
    """Extract text from a PDF using pypdf, stopping once the limit is reached."""
    from pypdf import PdfReader
    text_parts = []
    size = 0
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
                size += len(t) + 1
                if size >= limit:
                    break
    except Exception as e:
        logger.warning(f"PDF extract failed for {pdf_path}: {e}")
        return ""
    full = "\n".join(text_parts)
    return full[:limit]
