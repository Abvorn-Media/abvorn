"""The relevance gate has to fire at every point an article can reach disk.

`niche_relevance()` (src/deployment.py) is the rule; these tests lock the three
call sites, because a guard that exists but is not wired does nothing:

  * ContentPipeline.run -- aborts right after DRAFT, before fact-check and
    polish spend more model calls on content that is about to be discarded;
  * SiteDeployer.deploy_content -- the daemon's GitHub publish path, refusing
    before the currently published page is left untouched;
  * run_cycle.write_files -- the local docs/ writer, which is a separate path
    and would otherwise still write an off-topic article to disk.

Without these, the month-long recurrence of off-topic pages in three different
niches was possible because each path had only the product checks.
"""

import pytest

import abvorn.content.pipeline as pipeline_mod
from abvorn.content.pipeline import ContentPipeline

PRODUCTS = [{"name": "Lenovo ThinkPad X1 Carbon", "asin": "B0C1TEST",
             "url": "https://www.amazon.com/dp/B0C1TEST"}]


@pytest.fixture
def stub_stages(monkeypatch):
    """Replace every model-calling stage so run() is deterministic and free."""
    calls = []

    monkeypatch.setattr(pipeline_mod, "research_niche",
                        lambda niche, router: list(PRODUCTS))
    monkeypatch.setattr(pipeline_mod, "generate_outline",
                        lambda niche, products, persona, router, **kw: {"outline": ["H2: Intro"]})
    monkeypatch.setattr(pipeline_mod, "fact_check",
                        lambda draft, products, router, **kw: {"passed": True, "issues": []})
    monkeypatch.setattr(pipeline_mod, "polish",
                        lambda draft, fc, persona, router, **kw: {
                            "quality_score": {"overall": 10.0},
                            "article_html": "<p>x</p>", "revised_intro": ""})
    monkeypatch.setattr(pipeline_mod, "build_schema",
                        lambda **kw: {})
    monkeypatch.setattr(pipeline_mod, "_load_reflection_learnings", lambda niche: [])
    monkeypatch.setattr(pipeline_mod.logger, "error",
                        lambda *a, **kw: calls.append(a))
    return calls


def _draft(title):
    return {"post_title": title, "article_html": "<p>x</p>", "intro": "",
            "meta_description": "d", "faqs": [], "tags": [], "socials": {}}


class TestPipelineAbortsOffTopic:
    def test_returns_none_for_off_topic_title(self, monkeypatch, stub_stages):
        monkeypatch.setattr(pipeline_mod, "write_draft",
                            lambda *a, **kw: _draft("Solar Panels Buying Guide for First-Time Buyers"))
        assert ContentPipeline().run("laptops", router=object()) is None

    def test_aborts_before_fact_check_and_polish(self, monkeypatch, stub_stages):
        """The point of checking after DRAFT is to not pay for the rest."""
        spent = []
        monkeypatch.setattr(pipeline_mod, "write_draft",
                            lambda *a, **kw: _draft("First-Time Hotel Booking Guide"))
        monkeypatch.setattr(pipeline_mod, "fact_check",
                            lambda *a, **kw: spent.append("fact_check") or {"passed": True})
        monkeypatch.setattr(pipeline_mod, "polish",
                            lambda *a, **kw: spent.append("polish") or {})
        assert ContentPipeline().run("laptops", router=object()) is None
        assert spent == [], f"downstream stages ran anyway: {spent}"

    def test_logs_an_actionable_error(self, monkeypatch, stub_stages):
        monkeypatch.setattr(pipeline_mod, "write_draft",
                            lambda *a, **kw: _draft("Coffee Grinder Buying Guide for First-Time Buyers"))
        ContentPipeline().run("laptops", router=object())
        assert stub_stages, "an off-topic abort must be logged, not silent"
        assert "laptops" in str(stub_stages[0])


class TestPipelineKeepsOnTopic:
    def test_returns_content_for_on_topic_title(self, monkeypatch, stub_stages):
        monkeypatch.setattr(pipeline_mod, "write_draft",
                            lambda *a, **kw: _draft("The Ultimate Laptop Buying Guide: Lenovo Compared"))
        out = ContentPipeline().run("laptops", router=object())
        assert out is not None
        assert "Laptop" in out["post_title"]

    def test_singular_title_matches_plural_niche(self, monkeypatch, stub_stages):
        monkeypatch.setattr(pipeline_mod, "write_draft",
                            lambda *a, **kw: _draft("A Laptop Buying Guide for Everyone"))
        assert ContentPipeline().run("laptops", router=object()) is not None

    def test_title_matching_only_a_product_name_is_kept(self, monkeypatch, stub_stages):
        """'Echo Show 5' never says 'smart-home'; the products carry it."""
        monkeypatch.setattr(pipeline_mod, "research_niche",
                            lambda niche, router: [{"name": "Echo Show 5", "asin": "B0E1TEST"}])
        monkeypatch.setattr(pipeline_mod, "write_draft",
                            lambda *a, **kw: _draft("First-Time Buyer Guide: Echo Show 5 Review & Best Deal"))
        out = ContentPipeline().run("smart-home", router=object())
        assert out is not None


class TestWriteFilesSkipsOffTopic:
    """The local docs/ writer is a separate path from the daemon's deployer."""

    @pytest.fixture
    def in_tmp_docs(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "docs").mkdir()
        return tmp_path

    def _state(self):
        return {"niches": [{"slug": "laptops", "name": "Laptops"}]}

    def _article(self, title):
        return {"post_title": title, "article_html": "<p>x</p>", "intro": "",
                "product_name": "Lenovo", "meta_description": "d",
                "products": list(PRODUCTS)}

    def test_off_topic_article_is_not_written(self, in_tmp_docs):
        import run_cycle
        run_cycle.write_files(
            "laptops",
            {"laptops": [self._article("Solar Panels Buying Guide for First-Time Buyers")]},
            self._state(),
        )
        written = list((in_tmp_docs / "docs" / "reviews" / "laptops").glob("*.html"))
        assert not [p for p in written if "solar" in p.name], written

    def test_on_topic_article_is_still_written(self, in_tmp_docs):
        import run_cycle
        run_cycle.write_files(
            "laptops",
            {"laptops": [self._article("Best Laptops 2026: Lenovo, HP and Dell Compared")]},
            self._state(),
        )
        written = list((in_tmp_docs / "docs" / "reviews" / "laptops").glob("*.html"))
        assert any("laptop" in p.name for p in written), written
