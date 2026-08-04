# abvorn/core/brain.py

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from abvorn.core.neural_memory import get_neural_memory

logger = logging.getLogger(__name__)


def _local_index_ready() -> bool:
    """True when the repo's SQLite brain index already has documents."""
    try:
        from abvorn.brain.orchestrator import BRAIN_DB_PATH

        if not Path(BRAIN_DB_PATH).exists():
            return False
        from abvorn.brain.indexer import KnowledgeIndex

        return KnowledgeIndex(str(BRAIN_DB_PATH)).get_document_count() > 0
    except Exception:
        return False


class Brain:
    """
    Unified interface for querying Abvorn's knowledge base.
    Primary: Graphify (relationships, insights)
    Fallback: the repo's keyword/vector retriever (abvorn.brain.indexer/retriever)
    """

    def __init__(self, library_path: str = "C:\\Users\\Jean Mare\\Downloads\\Notebook LM Brain-20260803T004108Z-1-001\\Notebook LM Brain"):
        self.library_path = Path(library_path)
        self.memory = get_neural_memory()
        self.category_map = self._load_category_map()
        self.is_ready = self.memory.get_state().get("entities", 0) > 0 or _local_index_ready()

    def _load_category_map(self) -> dict:
        """Load the category-to-function mapping."""
        map_file = Path("data/brain_category_map.json")
        if map_file.exists():
            try:
                return json.loads(map_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Category map read failed: {e}")
        return {}

    def query(self, question: str, limit: int = 5) -> list:
        """
        Query the brain. Uses Graphify first, then the indexed retriever as fallback.
        """
        results = []

        # 1. PRIMARY: Graphify query (relationships, insights)
        try:
            graph_results = self.memory.query(question)
            if graph_results:
                for r in graph_results[:limit]:
                    results.append({
                        "source": r.get("source", "Graph"),
                        "insight": r.get("insight", r.get("text", ""))[:500],
                        "type": "graph",
                        "relevance": r.get("confidence", 0.7),
                    })
                return results
        except Exception as e:
            logger.warning(f"Graphify query failed: {e}")

        # 2. FALLBACK: indexed retriever (abvorn/brain)
        try:
            from abvorn.brain.orchestrator import get_brain_retriever

            retriever = get_brain_retriever()
            categories = self._get_categories_for_query(question)
            chunks = retriever.query(question, top_k=limit, domain_filter=categories)
            for r in chunks:
                results.append({
                    "source": r.get("title", "Unknown"),
                    "insight": r.get("text", "")[:500],
                    "type": "vector",
                    "relevance": r.get("relevance", 0.6),
                })
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")

        return results

    def _query_categories(self, question: str) -> Optional[List[str]]:
        """Determine which library categories to search (returns None if none matched)."""
        question_lower = question.lower()
        matched = []
        for category, data in self.category_map.items():
            for keyword in data.get("keywords", []):
                if keyword and keyword in question_lower:
                    matched.append(category)
                    break
        return matched if matched else None

    def _get_categories_for_query(self, question: str) -> Optional[str]:
        """Return a single domain filter for the retriever (or None)."""
        cats = self._query_categories(question)
        return cats[0] if cats else None

    def get_insights_for_function(self, function: str) -> List[Dict]:
        """Get insights for a specific system function."""
        categories = [
            cat for cat, data in self.category_map.items()
            if data.get("function") == function
        ]
        if not categories:
            return []
        query = f"What insights from {', '.join(categories)} apply to {function}?"
        return self.query(query, limit=10)

    def get_connections(self, concept_a: str, concept_b: str) -> List[Dict]:
        """Find connections between two concepts using Graphify."""
        query = f"How is {concept_a} related to {concept_b}?"
        return self.memory.query(query)

    def discover_patterns(self) -> List[Dict]:
        """Automatically discover patterns across the graph."""
        pattern_queries = [
            "What concepts appear most frequently across AI and Strategy books?",
            "What patterns exist between consumer psychology and decision-making?",
            "How do autonomous systems relate to business growth?",
            "What are the cross-cutting themes in the library?",
        ]
        patterns = []
        for q in pattern_queries:
            results = self.memory.query(q)
            if results:
                patterns.append({
                    "query": q,
                    "insights": results[:3],
                    "timestamp": datetime.now().isoformat(),
                })
        return patterns

    def get_category_report(self) -> dict:
        """Get a report of all categories and their book counts."""
        report = {}
        if not self.library_path.exists():
            return {}
        for category in self.library_path.iterdir():
            if category.is_dir():
                book_count = len(list(category.glob("*.pdf")))
                report[category.name] = book_count
        return report


# Singleton
_brain = None


def get_brain() -> Brain:
    global _brain
    if _brain is None:
        _brain = Brain()
    return _brain