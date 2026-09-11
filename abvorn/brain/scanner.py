"""Walks the brain directory, detects new/modified PDFs, extracts text."""

import hashlib, logging, os
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

# Wall-clock cap per file. One corrupt/pathological PDF (e.g. broken xref that
# makes pypdf rebuild the cross-reference table repeatedly) must never be able
# to hang a brain refresh indefinitely.
EXTRACT_TIMEOUT_S = 45

# Paths that already hit the timeout this process. Refresh is incremental (files
# are skipped once indexed), and a malformed PDF gets skipped by the extraction
# already, so keeping this in-memory is enough to avoid a fresh stall on every
# refresh without persisting junk.
_EXTRACT_FAILURES = set()


def _extract_pdf_text(pdf_path: str, limit: int) -> str:
    from pypdf import PdfReader
    text_parts = []
    size = 0
    reader = PdfReader(pdf_path)
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text_parts.append(t)
            size += len(t) + 1
            if size >= limit:
                break
    return "\n".join(text_parts)[:limit]


def extract_text(pdf_path: str, limit: int = TEXT_LIMIT, timeout: float = EXTRACT_TIMEOUT_S) -> str:
    """Extract text from a PDF using pypdf, bounded by wall-clock timeout.

    If extraction has already timed out for this path in this process, it is
    skipped immediately so a corrupt file can't block every refresh. On timeout
    the worker thread is detached (it can't be interrupted from outside); the
    in-process skip list prevents it from being re-spawned on later runs.
    """
    if pdf_path in _EXTRACT_FAILURES:
        return ""
    from concurrent.futures import TimeoutError as _FutTimeout
    from concurrent.futures import ThreadPoolExecutor

    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="brain-extract")
    future = executor.submit(_extract_pdf_text, pdf_path, limit)
    try:
        return future.result(timeout=timeout)
    except _FutTimeout:
        _EXTRACT_FAILURES.add(pdf_path)
        logger.warning(f"PDF extract timed out after {timeout:.0f}s: {pdf_path}")
        return ""
    except Exception as e:
        logger.warning(f"PDF extract failed for {pdf_path}: {e}")
        return ""
    finally:
        executor.shutdown(wait=False)
