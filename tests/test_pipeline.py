import json
import pytest
from abvorn.content.pipeline import ContentPipeline


def test_pipeline_full_run():
    """Pipeline should produce a complete content dict with all required fields."""

    class FakeRouter:
        def ask(self, prompt, **kw):
            return json.dumps({
                "outline": ["H2: Introduction", "H2: Product Review"],
                "title": "Test Title",
                "meta_description": "Test meta description for SEO purposes here it is long enough",
                "intro": "<p>Test intro</p>",
                "article_html": "<p>Test article</p>",
                "faqs": [{"question": "Q1?", "answer": "A1."}],
                "tags": ["test"],
                "socials": {"x": "tweet", "linkedin": "post"}
            })

    pipeline = ContentPipeline()
    result = pipeline.run("test_niche", FakeRouter(), persona={})
    assert result is not None
    assert "post_title" in result
    assert "article_html" in result
    assert "meta_description" in result
