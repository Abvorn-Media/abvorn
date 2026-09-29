"""Indexes extracted text into a queryable SQLite store with keyword + semantic search."""

import logging, hashlib, re, sqlite3, threading
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger("abvorn.brain.indexer")

STOPWORDS = {"the","a","an","is","are","was","were","be","been","being",
             "have","has","had","do","does","did","will","would","shall",
             "should","may","might","must","can","could","i","you","he",
             "she","it","we","they","this","that","these","those","and",
             "or","but","not","nor","for","with","on","at","in","of",
             "to","by","from","as","into","through","during","before",
             "after","above","below","between","out","off","over","under"}

class KnowledgeIndex:
    """SQLite-indexed knowledge base with keyword and embedding search."""

    def __init__(self, db_path):
        self._db_path = db_path
        self._conn = None
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    @contextmanager
    def _cursor(self):
        # One connection for the whole index, guarded by a lock. A per-thread
        # connection leaked one per thread: brain_server runs a
        # ThreadingHTTPServer, so every request opened a fresh WAL connection
        # that was never closed. That accumulated to 10.4GB of page cache and
        # OOM-killed the 24GB host (journald, snapd and sshd died with it).
        with self._lock:
            conn = self._connect()
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            finally:
                cursor.close()

    def close(self):
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def _init_db(self):
        with self._cursor() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL,
                    title TEXT NOT NULL,
                    path TEXT,
                    hash TEXT,
                    indexed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER NOT NULL REFERENCES documents(id),
                    chunk_index INT NOT NULL,
                    text TEXT NOT NULL,
                    tokens TEXT
                );
                CREATE TABLE IF NOT EXISTS domain_tags (
                    domain TEXT PRIMARY KEY,
                    keywords TEXT NOT NULL,
                    summary TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_tokens ON chunks(tokens);
            """)

    def _tokenize(self, text: str) -> str:
        tokens = re.findall(r'\b[a-z]{3,}\b', text.lower())
        return " ".join(t for t in tokens if t not in STOPWORDS)

    def _chunk_text(self, text: str, max_chars: int = 1500) -> list[str]:
        paragraphs = text.split("\n\n")
        chunks = []
        current = ""
        for p in paragraphs:
            stripped = p.strip()
            if not stripped:
                continue
            if len(current) + len(stripped) < max_chars:
                current += "\n\n" + stripped if current else stripped
            else:
                if current:
                    chunks.append(current)
                current = stripped
        if current:
            chunks.append(current)
        return chunks if chunks else [text[:max_chars]]

    def ingest_text(self, domain: str, title: str, text: str, path: str = "", file_hash: str = "") -> int:
        # Store the scan-time file hash when available so incremental refresh can
        # dedupe by path+hash; fall back to a content hash for text-only ingests.
        stored_hash = file_hash or hashlib.md5(text[:8192].encode()).hexdigest()
        with self._cursor() as c:
            if path:
                # Idempotent ingest. Concurrent refresh_brain() calls used to both
                # see "not indexed" and both INSERT, so every refresh appended
                # another copy of every PDF: the index reached 87,151 documents
                # and 10.4GB. The lookup and the insert now share one lock
                # acquisition, so the check-then-write is atomic. An unchanged
                # file is a no-op; a changed one replaces its old rows.
                for doc_id, prev_hash in c.execute(
                    "SELECT id, hash FROM documents WHERE path=?", (path,)
                ).fetchall():
                    if prev_hash == stored_hash:
                        return doc_id
                    c.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
                    c.execute("DELETE FROM documents WHERE id=?", (doc_id,))

            chunks = self._chunk_text(text)
            c.execute("INSERT INTO documents (domain, title, path, hash, indexed_at) VALUES (?, ?, ?, ?, ?)",
                      (domain, title, path, stored_hash, datetime.now().isoformat()))
            doc_id = c.lastrowid
            for i, chunk in enumerate(chunks):
                tokens = self._tokenize(chunk)
                c.execute("INSERT INTO chunks (doc_id, chunk_index, text, tokens) VALUES (?, ?, ?, ?)",
                          (doc_id, i, chunk, tokens))
            all_tokens = self._tokenize(text)
            c.execute("INSERT OR REPLACE INTO domain_tags (domain, keywords) VALUES (?, ?)",
                      (domain, all_tokens[:500]))
        logger.info(f"Indexed '{title}': {len(chunks)} chunks in domain '{domain}'")
        return doc_id

    def ingest_pdf(self, pdf_path: str, domain: str, text: str, file_hash: str = "") -> int:
        title = Path(pdf_path).stem
        return self.ingest_text(domain, title, text, pdf_path, file_hash)

    def get_domain_keywords(self, domain: str) -> str:
        with self._cursor() as c:
            c.execute("SELECT keywords FROM domain_tags WHERE domain=?", (domain,))
            row = c.fetchone()
            return row[0] if row else ""

    def get_document_count(self) -> int:
        with self._cursor() as c:
            c.execute("SELECT COUNT(*) FROM documents")
            return c.fetchone()[0]

    def get_indexed_paths(self) -> set:
        """Return the set of file paths already indexed (for incremental refresh)."""
        with self._cursor() as c:
            c.execute("SELECT path FROM documents WHERE path IS NOT NULL AND path != ''")
            return {row[0] for row in c.fetchall()}

    def get_chunk_count(self) -> int:
        with self._cursor() as c:
            c.execute("SELECT COUNT(*) FROM chunks")
            return c.fetchone()[0]
