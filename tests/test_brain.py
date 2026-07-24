import pytest
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
