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


class _AlwaysJsonRouter:
    """Router returning a fixed JSON payload, whatever it is asked."""

    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    def ask(self, prompt, **kw):
        self.prompts.append(prompt)
        return json.dumps(self.payload)


def test_pipeline_survives_polish_returning_none(monkeypatch):
    """polish() returning None used to crash the cycle with
    "'NoneType' object has no attribute 'get'" AFTER the draft and fact-check
    calls were already paid for. The draft must still be published."""
    from abvorn.content import pipeline as pipeline_mod

    monkeypatch.setattr(pipeline_mod, "polish", lambda *a, **k: None)

    router = _AlwaysJsonRouter({
        "outline": ["H2: Introduction"],
        "post_title": "Best Test Niche 2026",
        "title": "Best Test Niche 2026",
        "meta_description": "A test meta description that is long enough for search results.",
        "intro": "<p>Test intro</p>",
        "article_html": "<p>Test article body</p>",
        "faqs": [{"question": "Q1?", "answer": "A1."}],
        "tags": ["test"],
        "socials": {"x": "tweet"},
    })
    result = ContentPipeline().run("test_niche", router, persona={})

    assert result is not None
    assert result["intro"] == "<p>Test intro</p>"
    assert result["article_html"] == "<p>Test article body</p>"
    assert result["quality_score"] == 7.0


def test_write_draft_retries_truncated_json_with_compact_contract():
    """A long draft that is cut off mid-string used to fail the whole stage.
    The retry must ask for a shorter draft with a closed JSON object."""
    from abvorn.agents.writer import write_draft

    class TruncatingThenValidRouter:
        def __init__(self):
            self.prompts = []

        def ask(self, prompt, **kw):
            self.prompts.append(prompt)
            if len(self.prompts) == 1:
                return '{"post_title": "Best X", "article_html": "<p>cut off mid-'
            return json.dumps({
                "post_title": "Best X 2026",
                "article_html": "<p>Short but complete article.</p>",
            })

    router = TruncatingThenValidRouter()
    result = write_draft("test", [], {"outline": ["H2: Intro"]}, {}, [], router)

    assert result["post_title"] == "Best X 2026"
    assert len(router.prompts) == 2
    assert "600-900 words" in router.prompts[1]
    assert "No <table>" in router.prompts[1]


def test_pipeline_tolerates_outline_entries_as_dicts():
    """A model that returns outline objects instead of strings used to kill the
    cycle with "sequence item 0: expected str instance, dict found"."""
    router = _AlwaysJsonRouter({
        "outline": [
            {"heading": "H2: Introduction", "description": "why this matters"},
            {"heading": "H2: Product Review", "description": "the picks"},
        ],
        "post_title": "Best Test Niche 2026",
        "title": "Best Test Niche 2026",
        "meta_description": "A test meta description that is long enough for search results.",
        "intro": "<p>Test intro</p>",
        "article_html": "<p>Test article body</p>",
        "faqs": [{"question": "Q1?", "answer": "A1."}],
        "tags": ["test"],
        "socials": {"x": "tweet"},
    })
    result = ContentPipeline().run("test_niche", router, persona={})

    assert result is not None
    draft_prompts = [p for p in router.prompts if "OUTLINE TO FOLLOW" in p]
    assert draft_prompts, "draft prompt was never built"
    assert "H2: Introduction" in draft_prompts[0]
    assert "why this matters" in draft_prompts[0]
