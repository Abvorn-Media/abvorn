import pytest, json
from abvorn.factory.pipeline import PersuasionPipeline


def test_persuasion_pipeline_output():
    """Should produce a complete content bundle."""
    pipeline = PersuasionPipeline()
    persona = {
        "name": "Marcus the Commuter",
        "psychology": {
            "awareness_level": "solution_aware",
            "primary_lf8_desire": "freedom_from_pain",
            "anxieties": ["battery dying", "tangled wires"],
            "hopes": ["peaceful commute"]
        }
    }

    class FakeRouter:
        def ask(self, prompt, **kw):
            return json.dumps({
                "post_title": "Best Wireless Headphones for Commuters in 2026",
                "meta_description": "Tired of tangled wires on your commute? We tested 20+ pairs to find the perfect ones.",
                "intro": "<p>Your commute should be your sanctuary.</p>",
                "article_html": "<p>Full review content here.</p>",
                "lead_magnet_title": "Commuter Headphone Cheat Sheet",
                "lead_magnet_description": "5 questions to find your perfect pair",
                "lead_magnet_content": "1. Do you need ANC? 2. Battery life...",
                "tags": ["wireless headphones", "commuter", "buying guide"],
                "selected_angle": "problem_solution"
            })

    result = pipeline.run("wireless headphones", persona, FakeRouter())
    assert result is not None
    assert "post_title" in result
    assert "lead_magnet" in result or "lead_magnet_title" in result
    assert len(result.get("tags", [])) > 0


def test_pipeline_without_brain():
    """Should work without a brain retriever."""
    pipeline = PersuasionPipeline()
    persona = {"name": "Test", "psychology": {"anxieties": ["test"]}}

    class FakeRouter:
        def ask(self, prompt, **kw):
            return {"post_title": "Test Post", "tags": ["test"], "selected_angle": "review"}

    result = pipeline.run("test niche", persona, FakeRouter())
    assert result is not None
    assert result["post_title"] == "Test Post"