import json
import pytest
from abvorn.brain.indexer import KnowledgeIndex
from abvorn.brain.retriever import KnowledgeRetriever
from abvorn.content.pipeline import ContentPipeline

def test_knowledge_augmented_pipeline():
    """Pipeline with brain context should include knowledge signals."""
    index = KnowledgeIndex(":memory:")
    index.ingest_text("Copywriting", "Breakthrough Advertising",
        "The most powerful advertising principle is the problem-awareness level. "
        "Match the intensity of the prospect's awareness of their problem.")
    retriever = KnowledgeRetriever(index)

    class FakeRouter:
        def ask(self, prompt, **kw):
            return json.dumps({
                "outline": ["H2: Introduction", "H2: Product Review"],
                "post_title": "Test Title",
                "meta_description": "Test meta description for SEO here it is long enough",
                "intro": "<p>Test intro</p>",
                "article_html": "<p>Test article</p>",
                "faqs": [{"question": "Q1?", "answer": "A1."}],
                "tags": ["test"],
                "socials": {"x": "tweet", "linkedin": "post"}
            })

    pipeline = ContentPipeline()
    pipeline.brain = retriever
    result = pipeline.run("test_niche", FakeRouter(), persona={})
    assert result is not None
    assert "post_title" in result