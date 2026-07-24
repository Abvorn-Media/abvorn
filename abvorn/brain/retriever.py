"""Queries the knowledge index using keyword matching and returns relevant chunks."""

import json, logging, re, sqlite3

logger = logging.getLogger("abvorn.brain.retriever")

STOPWORDS = {"the","a","an","is","are","was","were","be","been","being",
             "have","has","had","do","does","did","will","would","shall",
             "should","may","might","must","can","could","i","you","he",
             "she","it","we","they","this","that","these","those","and",
             "or","but","not","nor","for","with","on","at","in","of",
             "to","by","from","as","into","through","during","before",
             "after","above","below","between","out","off","over","under"}

class KnowledgeRetriever:
    """Retrieves knowledge chunks relevant to a query using keyword scoring."""

    def __init__(self, index):
        self._index = index
        self._domain_cache = {}

    def _tokenize(self, text: str) -> set:
        return set(re.findall(r'\b[a-z]{3,}\b', text.lower())) - STOPWORDS

    def query(self, query_text: str, top_k: int = 10, domain_filter: str = None) -> list[dict]:
        query_tokens = self._tokenize(query_text)
        if not query_tokens:
            return []

        with self._index._cursor() as c:
            if domain_filter:
                c.execute("""
                    SELECT c.id, c.text, c.tokens, d.domain, d.title
                    FROM chunks c JOIN documents d ON c.doc_id = d.id
                    WHERE d.domain = ?
                """, (domain_filter,))
            else:
                c.execute("""
                    SELECT c.id, c.text, c.tokens, d.domain, d.title
                    FROM chunks c JOIN documents d ON c.doc_id = d.id
                """)

            scored = []
            for row in c.fetchall():
                chunk_id, text, tokens_field, domain, title = row
                if not tokens_field:
                    continue
                chunk_tokens = set(tokens_field.split())
                overlap = len(query_tokens & chunk_tokens)
                if overlap > 0:
                    scored.append((overlap / len(query_tokens), {
                        "id": chunk_id,
                        "text": text[:2000],
                        "domain": domain,
                        "title": title,
                        "relevance": round(overlap / len(query_tokens), 2),
                    }))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:top_k]]

    def query_for_pipeline(self, niche: str, angle: str = "", persona: dict = None) -> dict:
        """Build a context bundle for the content pipeline."""
        query_parts = [niche, angle]
        if persona:
            query_parts.extend(persona.get("frustrations", []))
            query_parts.extend(persona.get("desires", []))
        query = " ".join(query_parts)

        chunks = self.query(query, top_k=8)
        results = {"chunks": chunks, "total": len(chunks)}

        if chunks:
            results["copywriting_principles"] = [
                c for c in chunks if c["domain"] in ("Copywriting",)
            ]
            results["psychology_triggers"] = [
                c for c in chunks if c["domain"] in ("Consumer_Psychology_and_Buyer_Behavior",)
            ]
            results["seo_tactics"] = [
                c for c in chunks if c["domain"] in ("SEO", "Conversion_Rate_Optimisation",)
            ]

        return results

    def summarize_knowledge_base(self) -> dict:
        """Return a summary of what's in the brain."""
        with self._index._cursor() as c:
            c.execute("""
                SELECT d.domain, COUNT(*) as doc_count, COUNT(c.id) as chunk_count
                FROM documents d LEFT JOIN chunks c ON c.doc_id = d.id
                GROUP BY d.domain ORDER BY doc_count DESC
            """)
            domains = []
            for row in c.fetchall():
                domains.append({"domain": row[0], "documents": row[1], "chunks": row[2]})
            c.execute("SELECT SUM(c) FROM (SELECT COUNT(*) as c FROM documents UNION ALL SELECT COUNT(*) FROM chunks)")
            total_docs = sum(r["documents"] for r in domains)
            total_chunks = sum(r["chunks"] for r in domains)
            return {"domains": domains, "total_documents": total_docs, "total_chunks": total_chunks}
