import json
from datetime import date

import pytest
from abvorn.content.pipeline import ContentPipeline


class _PromptCaptureRouter:
    """Router that records every prompt sent to it."""

    def __init__(self):
        self.prompts = []

    def ask(self, prompt, **kw):
        self.prompts.append(prompt)
        return json.dumps({
            "outline": ["H2: Introduction", "H2: Product Review"],
            "title": "Test Title",
            "meta_description": "Test meta description for SEO purposes here it is long enough",
            "intro": "<p>Test intro</p>",
            "article_html": "<p>Test article</p>",
            "faqs": [{"question": "Q1?", "answer": "A1."}],
            "tags": ["test"],
            "socials": {"x": "tweet", "linkedin": "post"},
        })


def test_prompts_anchor_generated_copy_to_current_year():
    """Writer prompts must state the real current year so titles don't ship
    a stale year (a 'Best X 2025' guide published in 2026)."""
    router = _PromptCaptureRouter()
    pipeline = ContentPipeline()
    pipeline.run("test_niche", router, persona={})

    combined = "\n".join(router.prompts)
    today = date.today()
    assert str(today.year) in combined
    assert "TODAY IS" in combined
    assert f"current year is {today.year}" in combined


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
