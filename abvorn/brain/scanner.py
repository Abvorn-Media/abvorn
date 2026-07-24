"""Walks the brain directory, detects new/modified PDFs, extracts text."""

import hashlib, logging, json, os, re
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("abvorn.brain.scanner")

BRAIN_PATH = Path(os.environ.get("ABVORN_BRAIN_PATH", ""))
DEFAULT_PATHS = [
    BRAIN_PATH,
    Path("/content/drive/MyDrive/Notebook LM Brain"),
    Path.home() / ".abvorn" / "brain",
]

def _find_brain() -> Path:
    for p in DEFAULT_PATHS:
        if p.exists():
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
            pdfs = list(entry.glob("*.pdf")) + list(entry.glob("*.PDF"))
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

def extract_text(pdf_path: str) -> str:
    """Extract text from a PDF file using pdfplumber."""
    import pdfplumber
    text_parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
    except Exception as e:
        logger.warning(f"PDF extract failed for {pdf_path}: {e}")
        return ""
    full = "\n".join(text_parts)
    return full[:50000]
