"""Indexes extracted text into a queryable SQLite store with keyword + semantic search."""

import json, logging, hashlib, re, sqlite3, threading
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
        self._local = threading.local()
        self._init_db()

    @contextmanager
    def _cursor(self):
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path))
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        yield self._local.conn.cursor()
        self._local.conn.commit()

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
        chunks = self._chunk_text(text)
        doc_hash = hashlib.md5(text[:8192].encode()).hexdigest()
        with self._cursor() as c:
            c.execute("INSERT INTO documents (domain, title, path, hash, indexed_at) VALUES (?, ?, ?, ?, ?)",
                      (domain, title, path, doc_hash, datetime.now().isoformat()))
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
