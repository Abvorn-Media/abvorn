import pytest
import sqlite3
import threading
from pathlib import Path
from abvorn.brain.indexer import KnowledgeIndex
from abvorn.brain.retriever import KnowledgeRetriever

def test_index_and_retrieve():
    """Should index a test PDF and retrieve knowledge from it."""
    index = KnowledgeIndex(":memory:")
    index.ingest_text("test_domain", "Test Doc", "This is a psychological principle about buying behavior. Scarcity increases desire.")
    retriever = KnowledgeRetriever(index)
    results = retriever.query("buying behavior", top_k=5)
    assert len(results) > 0
    assert "scarcity" in results[0]["text"].lower()

def test_index_reuses_one_connection_across_threads(monkeypatch, tmp_path):
    """Regression: a per-thread connection leaked one per request.

    brain_server runs a ThreadingHTTPServer, so every HTTP request opened a
    fresh SQLite connection that was never closed. That grew to 10.4GB of page
    cache and OOM-killed the 24GB host. The index must hold exactly one
    connection no matter how many threads use it.
    """
    calls = []
    real_connect = sqlite3.connect

    def counting_connect(*args, **kwargs):
        calls.append(args[0] if args else None)
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", counting_connect)

    index = KnowledgeIndex(str(tmp_path / "brain.db"))
    index.ingest_text("d", "T", "scarcity increases desire in buying behavior")

    def worker():
        for _ in range(5):
            index.get_document_count()

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(calls) == 1, (
        f"expected 1 sqlite connection for the whole index, got {len(calls)} "
        f"from 20 threads - connections are leaking"
    )

def test_orchestrator_reuses_one_index(monkeypatch, tmp_path):
    """Regression: the index was rebuilt per call, leaking a connection each time."""
    import abvorn.brain.orchestrator as orch

    monkeypatch.setattr(orch, "BRAIN_DB_PATH", tmp_path / "b.db")
    monkeypatch.setattr(orch, "_INDEX", None, raising=False)

    first = orch._get_index()
    second = orch._get_index()

    assert first is second, "refresh_brain/get_brain_retriever must reuse one index"

def test_index_close_releases_connection(tmp_path):
    """close() must drop the connection so a rebuilt index cannot hold stale pages."""
    index = KnowledgeIndex(str(tmp_path / "brain.db"))
    index.ingest_text("d", "T", "scarcity increases desire")
    assert index.get_document_count() == 1
    index.close()
    assert index._conn is None

def test_ingest_same_path_twice_does_not_duplicate(tmp_path):
    """Regression: every refresh appended another copy of every PDF.

    Two concurrent refresh_brain() calls both saw "not indexed" and both
    inserted, so documents/chunks grew without bound (87,151 documents,
    10.4GB). Re-ingesting an unchanged file must be a no-op.
    """
    index = KnowledgeIndex(str(tmp_path / "brain.db"))
    first = index.ingest_text("d", "T", "scarcity increases desire", path="/books/x.pdf", file_hash="h1")
    second = index.ingest_text("d", "T", "scarcity increases desire", path="/books/x.pdf", file_hash="h1")

    assert first == second
    assert index.get_document_count() == 1
    assert index.get_chunk_count() == 1

def test_concurrent_ingest_of_same_file_stores_one_copy(tmp_path):
    """Regression: the check-then-insert race that doubled every document."""
    index = KnowledgeIndex(str(tmp_path / "brain.db"))
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        index.ingest_text("d", "T", "scarcity increases desire in buying behavior",
                          path="/books/x.pdf", file_hash="h1")

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert index.get_document_count() == 1, "concurrent ingest must not duplicate documents"

def test_changed_hash_replaces_old_chunks(tmp_path):
    """A modified file must replace its rows, not accumulate alongside the old copy."""
    index = KnowledgeIndex(str(tmp_path / "brain.db"))
    index.ingest_text("d", "T", "scarcity increases desire", path="/books/x.pdf", file_hash="h1")
    index.ingest_text("d", "T", "scarcity increases desire a lot more", path="/books/x.pdf", file_hash="h2")

    assert index.get_document_count() == 1
    with index._cursor() as c:
        c.execute("SELECT hash FROM documents WHERE path=?", ("/books/x.pdf",))
        assert c.fetchone()[0] == "h2"
