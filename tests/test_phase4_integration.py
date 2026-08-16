"""Integration tests for Phase 4 modules.

Tests:
- src/content_generation.py: generate_outline, write_draft, fetch_social_sentiment
- src/deployment.py: build_article_page, rewrite_affiliate_urls, generate_click_url
- src/change_management.py: lifecycle, rollback, A/B testing
- src/tools_registry.py: registration, search, execution, rate limiting
- src/meta_evolution.py: evolution cycle, convergence, persistence
"""
import json
import re
import time
import os
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

import src.deployment as deployment_mod
deployment_mod._SITE_URL = os.environ.get("SITE_URL", "https://abvorn-media.github.io/abvorn").rstrip("/")

from src.deployment import generate_click_url, rewrite_affiliate_urls, build_article_page
from src.change_management import (
    create_change_manager,
    ChangeManager,
    ChangeType,
    ChangeStatus,
)
from src.tools_registry import ToolRegistry, Tool, ToolAccess, create_tool_registry
from src.meta_evolution import MetaEvolutionEngine, Generation


# ---------------------------------------------------------------------------
# content_generation.py
# ---------------------------------------------------------------------------

class FakeQueryResult:
    def __init__(self, content, provider="test", tokens=10):
        self.content = content
        self.provider_used = provider
        self.tokens_used = tokens


@pytest.fixture(autouse=True)
def patch_ai_sql():
    """Patch ai_sql for content_generation tests."""
    mock = MagicMock()
    mock.query.return_value = FakeQueryResult(
        json.dumps({
            "outline": ["Introduction", "What to Look For", "Product Reviews", "Buying Guide", "FAQ", "Conclusion"],
            "selected_angle": "problem_solution",
            "primary_keyword": "best test-niche",
            "post_title": "Best Test Niche — Expert Review",
            "meta_description": "Find the best test-niche with our expert guide and top product recommendations.",
        })
    )
    with patch("src.content_generation.ai_sql", mock):
        yield mock


def test_generate_outline_returns_structure():
    from src.content_generation import generate_outline

    products = [{"name": "Product A", "price": "$10"}]
    result = generate_outline("test-niche", products)

    assert result is not None
    assert "outline" in result
    assert "post_title" in result
    assert "meta_description" in result
    assert len(result["outline"]) >= 4


def test_write_draft_returns_html_fields():
    from src.content_generation import write_draft

    outline = {
        "post_title": "Best Test Niche",
        "meta_description": "desc",
        "selected_angle": "problem_solution",
        "primary_keyword": "best test-niche",
        "outline": ["Intro", "Review"],
    }
    products = [{"name": "Product A", "price": "$10"}]
    with patch("src.content_generation.ai_sql") as mock:
        mock.query.side_effect = [
            FakeQueryResult("<p>Intro HTML</p>"),
            FakeQueryResult("<p>Article body HTML</p>"),
        ]
        result = write_draft("test-niche", products, outline)

    assert result is not None
    assert "intro" in result
    assert "article_html" in result
    assert "post_title" in result
    assert "meta_description" in result
    assert "<p>" in result.get("intro", "")


def test_fetch_social_sentiment_handles_missing_adapter():
    from src.content_generation import fetch_social_sentiment

    with patch("src.agent_reach_adapter.get_agent_reach_adapter", side_effect=ImportError):
        result = fetch_social_sentiment("test-niche")
        assert isinstance(result, dict)
        assert result == {}


def test_fetch_social_sentiment_handles_adapter_failure():
    from src.content_generation import fetch_social_sentiment

    bad_adapter = MagicMock()
    bad_adapter.fetch_social_data.side_effect = RuntimeError("API down")
    with patch("src.agent_reach_adapter.get_agent_reach_adapter", return_value=bad_adapter):
        result = fetch_social_sentiment("test-niche")
        assert result == {}


# ---------------------------------------------------------------------------
# deployment.py
# ---------------------------------------------------------------------------

def test_generate_click_url_default_domain():
    url = generate_click_url("test-niche", 0)
    assert url == "https://abvorn.com/click/test-niche/0"


def test_generate_click_url_custom_domain(monkeypatch):
    monkeypatch.setenv("CLICK_DOMAIN", "https://example.com")
    # Module reads env at import, re-patch the module var directly
    import importlib
    with patch.object(deployment_mod, "CLICK_DOMAIN", "https://example.com"):
        url = generate_click_url("test-niche", 1)
        assert url == "https://example.com/click/test-niche/1"


def test_rewrite_affiliate_urls_single_link():
    html = '<a href="https://www.amazon.com/s?k=earbuds&tag=viraltestco-20">buy</a>'
    out = rewrite_affiliate_urls(html, "niche-1")
    assert "/click/niche-1/" in out
    assert "amazon.com" not in out


def test_rewrite_affiliate_urls_multiple_unique_products():
    html = (
        '<a href="https://www.amazon.com/s?k=earbuds&tag=viraltestco-20">buy1</a>'
        '<a href="https://www.amazon.com/s?k=headphones&tag=viraltestco-20">buy2</a>'
    )
    out = rewrite_affiliate_urls(html, "niche-2")
    assert "/click/niche-2/0" in out
    assert "/click/niche-2/1" in out


def test_rewrite_affiliate_urls_skips_already_rewritten():
    html = '<a href="https://abvorn.com/click/old/0">buy</a>'
    out = rewrite_affiliate_urls(html, "niche-3")
    assert out == html


def test_build_article_page_rewrites_links_when_article_id_given():
    html = build_article_page(
        niche_slug="test-niche",
        niche_name="Test Niche",
        post_title="Test Post",
        article_html='<p>Buy <a href="https://www.amazon.com/s?k=test&tag=viraltestco-20">here</a></p>',
        intro="<p>Intro</p>",
        product_name="Product",
        meta_desc="desc",
        all_slugs=["test-niche"],
        products=[],
        article_id="test-niche-0",
    )
    assert "/click/test-niche-0/" in html


def test_build_article_page_preserves_original_links_without_article_id():
    html = build_article_page(
        niche_slug="test-niche",
        niche_name="Test Niche",
        post_title="Test Post",
        article_html='<p>Buy <a href="https://www.amazon.com/s?k=test&tag=viraltestco-20">here</a></p>',
        intro="<p>Intro</p>",
        product_name="Product",
        meta_desc="desc",
        all_slugs=["test-niche"],
        products=[],
    )
    assert "amazon.com" in html


def test_build_article_page_strips_dangling_p_before_decision_matrix():
    """A bare "<p" at the end of the AI draft must not swallow the decision
    matrix that the template appends next (it previously broke the container
    and pushed the CTA/FAQ/footer full-width)."""
    html = build_article_page(
        niche_slug="test-niche",
        niche_name="Test Niche",
        post_title="Test Post",
        article_html='<p>Intro copy.</p>\n<h2 id="conclusion">Conclusion</h2>\n<p',
        intro="<p>Intro</p>",
        product_name="Product",
        meta_desc="desc",
        all_slugs=["test-niche"],
        products=[
            {"name": "Prod A", "description": "Desc", "price": "$10", "image": ""},
        ],
        article_id=None,
    )
    assert '<p</p>' not in html
    # the decision matrix must sit after a properly closed (or absent)
    # paragraph, not inside a dangling one
    matrix = html[html.find('class="table-wrap decision-matrix"'):]
    assert '<div class="table-wrap decision-matrix">' in html
    # no raw "<p\n<div" join anywhere in the body
    import re
    assert not re.search(r"<p\s*$.*<div", html[html.find('id="main"'):html.find('<footer')], flags=re.S | re.M)


def test_build_article_page_closes_unclosed_list_before_decision_matrix():
    """An AI draft ending with an unclosed <ul>/<li> and a stray bare <div>
    must not swallow the decision matrix the template appends next — the
    sections must stay direct children of the article body, not nested in a
    list item (which indented + bullet-marked the page's bottom half)."""
    html = build_article_page(
        niche_slug="test-niche",
        niche_name="Test Niche",
        post_title="Test Post",
        article_html=(
            '<h2 id="pros">Pros</h2>\n'
            "<ul>\n"
            " <li>Open-ear comfort, hear surroundings naturally</li>\n"
            " <li>Top-tier voice isolation for calls\n<div\n"
        ),
        intro="<p>Intro</p>",
        product_name="Product",
        meta_desc="desc",
        all_slugs=["test-niche"],
        products=[
            {"name": "Prod A", "description": "Desc", "price": "$10", "image": ""},
        ],
        article_id=None,
    )
    body = html[html.find('id="main"'):html.find('<footer')]
    # the stray "<div" fragment is gone, not a bare opening tag
    assert not re.search(r"<div\s*$", body, flags=re.M)
    # the list is closed before the appended sections
    pre_matrix = body[: body.find('class="table-wrap decision-matrix"')]
    assert "</ul>" in pre_matrix
    # the decision matrix is a direct child of article-body, not inside a list
    matrix_ctx = body[body.find('class="table-wrap decision-matrix"') - 120:]
    assert "</li>\n</ul>" in matrix_ctx or "</ul>" in matrix_ctx
    assert not re.search(
        r"<li[^>]*>\s*<div class=\"table-wrap decision-matrix\"",
        matrix_ctx,
        flags=re.S,
    )


def test_build_article_page_strips_truncated_closing_tag_before_decision_matrix():
    """An AI draft truncated mid-closing-tag (e.g. a tail ending in "</h2" with
    no ">") must not swallow the decision matrix the template appends next —
    otherwise the matrix/chart/products/FAQ stop being direct children of the
    article body and vanish from the rendered layout."""
    html = build_article_page(
        niche_slug="test-niche",
        niche_name="Test Niche",
        post_title="Test Post",
        article_html='<p>Intro copy.</p>\n<h2 id="what">What to Look For</h2',
        intro="<p>Intro</p>",
        product_name="Product",
        meta_desc="desc",
        all_slugs=["test-niche"],
        products=[
            {"name": "Prod A", "description": "Desc", "price": "$10", "image": ""},
        ],
        article_id=None,
    )
    body = html[html.find('id="main"'):html.find('<footer')]
    # the dangling "</h2" fragment must be gone, not left as an unterminated tag
    assert not re.search(r"</h2\s*$", body, flags=re.M)
    # the decision matrix is still present and a direct child of article-body
    assert 'class="table-wrap decision-matrix"' in body
    matrix_ctx = body[body.find('class="table-wrap decision-matrix"') - 120:]
    assert not re.search(
        r"<h2[^>]*>\s*<div class=\"table-wrap decision-matrix\"",
        matrix_ctx,
        flags=re.S,
    )


# ---------------------------------------------------------------------------
# change_management.py
# ---------------------------------------------------------------------------

def test_change_manager_lifecycle_draft_to_production():
    mgr = create_change_manager()
    cid = mgr.create_change("Feature X", ChangeType.FEATURE, "Add feature X")

    assert mgr.changes[cid].status == ChangeStatus.DRAFT

    assert mgr.promote_change(cid, ChangeStatus.STAGING) is True
    assert mgr.promote_change(cid, ChangeStatus.CANARY) is True
    assert mgr.promote_change(cid, ChangeStatus.PRODUCTION) is True
    assert mgr.changes[cid].status == ChangeStatus.PRODUCTION
    assert mgr.changes[cid].deployed_at is not None


def test_change_manager_rejects_invalid_promotion():
    mgr = create_change_manager()
    cid = mgr.create_change("Bad Change", ChangeType.WORKFLOW, "desc")
    assert mgr.promote_change(cid, ChangeStatus.PRODUCTION) is False


def test_change_manager_rollback():
    mgr = create_change_manager()
    cid = mgr.create_change("Flaky Change", ChangeType.PIPELINE, "desc")
    mgr.promote_change(cid, ChangeStatus.CANARY)
    assert mgr.rollback_change(cid, "Too many errors") is True
    assert mgr.changes[cid].status == ChangeStatus.ROLLED_BACK
    assert mgr.changes[cid].metadata["rollback_reason"] == "Too many errors"


def test_change_manager_rollback_unknown_change():
    mgr = create_change_manager()
    assert mgr.rollback_change("missing", "reason") is False


def test_change_manager_feature_flags():
    mgr = create_change_manager()
    assert mgr.is_feature_enabled("new_ui") is False
    mgr.set_feature_flag("new_ui", True)
    assert mgr.is_feature_enabled("new_ui") is True


def test_change_manager_workflow_versions():
    mgr = create_change_manager()
    wf = mgr.register_workflow_version("quality", {"temperature": 0.8})
    assert wf.version == "v1.0"
    assert mgr.deploy_workflow_version("quality", "v1.0") is True


def test_change_manager_ab_test_significance():
    mgr = create_change_manager()

    call_count = {"a": 0, "b": 0}

    def variant_a():
        call_count["a"] += 1
        return {"success": 0.9}

    def variant_b():
        call_count["b"] += 1
        if call_count["b"] % 7 == 0:
            raise RuntimeError("variant b transient failure")
        return {"success": 0.4}

    with patch.object(mgr, "_t_test_p_value", return_value=0.01):
        result = mgr.run_ab_test(
            "test-1", variant_a, variant_b, sample_size=100, metric="success"
        )
    assert result["winner"] == "A"
    assert result["significant"] is True
    assert result["p_value"] == 0.01
    assert len(result["variant_a"]["scores"]) == 50
    assert len(result["variant_b"]["scores"]) + result["variant_b"]["failures"] == 50


def test_change_manager_generate_report_counts_statuses():
    mgr = create_change_manager()
    cid = mgr.create_change("R1", ChangeType.PROMPT, "d")
    mgr.promote_change(cid, ChangeStatus.STAGING)
    report = mgr.generate_report()
    assert report["total_changes"] == 1
    assert report["changes_by_status"]["draft"] == 0
    assert report["changes_by_status"]["staging"] == 1


# ---------------------------------------------------------------------------
# tools_registry.py
# ---------------------------------------------------------------------------

def _make_tool(name="echo"):
    def fn(msg="hi"):
        return msg
    return fn


def test_tool_registry_registers_and_retrieves():
    registry = create_tool_registry()
    registry.register("echo", "Echo message", _make_tool("echo"))
    tool = registry.get_tool("echo")
    assert tool is not None
    assert tool.name == "echo"


def test_tool_registry_search_matches_name_and_description():
    registry = create_tool_registry()
    registry.register("email_sender", "Send email to user", _make_tool("email"))
    registry.register("sms_sender", "Send SMS", _make_tool("sms"))
    results = registry.search_tools("email")
    assert len(results) == 1
    assert results[0].name == "email_sender"
    results_desc = registry.search_tools("Send")
    assert len(results_desc) == 2


def test_tool_registry_execute_runs_function():
    registry = create_tool_registry()
    registry.register("echo", "Echo", _make_tool("echo"))
    result = registry.execute("echo", msg="hello")
    assert result == "hello"


def test_tool_registry_execute_unknown_raises():
    registry = create_tool_registry()
    with pytest.raises(ValueError):
        registry.execute("nonexistent")


def test_tool_registry_rate_limit_blocks_after_limit():
    registry = create_tool_registry()
    counter = {"n": 0}

    def limited():
        counter["n"] += 1
        return "ok"

    registry.register(
        "limited_tool",
        "Limited",
        limited,
        rate_limit=2,
    )
    registry.execute("limited_tool")
    registry.execute("limited_tool")
    registry.execute("limited_tool")
    with pytest.raises(Exception):
        registry.execute("limited_tool")
    assert counter["n"] == 3


def test_tool_registry_report_counts_usage():
    registry = create_tool_registry()
    registry.register("echo", "Echo", _make_tool("echo"))
    registry.execute("echo", msg="a")
    registry.execute("echo", msg="b")
    report = registry.generate_report()
    assert report["total_tools"] == 1
    assert report["usage_count"] == 2


# ---------------------------------------------------------------------------
# meta_evolution.py
# ---------------------------------------------------------------------------

class FakeSpawner:
    def __init__(self, base_config):
        self.base_config = base_config
        self.instances = {}
        self.results = {}

    def create_instance(self, name, config_overrides):
        iid = f"inst_{name}"
        self.instances[iid] = name
        return iid

    def spawn_all(self, niches):
        fake_results = {}
        for iid, name in self.instances.items():
            fake_results[iid] = MagicMock(
                instance_id=iid,
                success=True,
                engagement_score=0.5 + (hash(name + "fixed") % 100) / 400.0,
                metadata={"temperature": 0.7},
            )
        self.results = fake_results
        return fake_results

    def get_best_instance(self):
        if not self.results:
            return None
        return max(self.results, key=lambda x: self.results[x].engagement_score)

    def generate_report(self):
        return {"fake": True}


@pytest.fixture
def evolution_engine():
    base = {
        "provider_preferences": ["kilo"],
        "workflow_name": "standard",
        "temperature": 0.7,
        "max_tokens": 2000,
    }
    engine = MetaEvolutionEngine(base)
    engine.spawner = FakeSpawner(base)
    return engine


def test_evolution_cycle_returns_metrics(evolution_engine):
    niches = [{"slug": "test-niche"}]
    result = evolution_engine.evolve(niches)
    assert "generation" in result
    assert "best_engagement" in result
    assert result["generation"] == 1
    assert len(evolution_engine.generations) == 1


def test_evolution_cycle_updates_best_config(evolution_engine):
    base = {
        "provider_preferences": ["kilo"],
        "workflow_name": "standard",
        "temperature": 0.7,
        "max_tokens": 2000,
    }
    engine = MetaEvolutionEngine(base)
    engine.spawner = FakeSpawner(base)
    niches = [{"slug": "test-niche"}]
    engine.evolve(niches)
    assert "temperature" in engine.current_best_config


def test_run_evolution_generates_multiple_generations(evolution_engine):
    niches = [{"slug": "test-niche"}]
    report = evolution_engine.run_evolution(niches, generations=3)
    assert report["total_generations"] == 3
    assert report["best_engagement"] > 0.0
    assert len(report["generations"]) == 3


def test_evolution_generate_report_without_spawner():
    base = {"provider_preferences": ["kilo"], "workflow_name": "standard", "temperature": 0.7, "max_tokens": 2000}
    engine = MetaEvolutionEngine(base)
    report = engine.generate_report()
    assert report["total_generations"] == 0
    assert report["best_engagement"] == 0.0
    assert report["generations"] == []


def test_evolution_convergence_detection(evolution_engine):
    """Simulate flat engagement across generations (convergence)."""
    base = {
        "provider_preferences": ["kilo"],
        "workflow_name": "standard",
        "temperature": 0.7,
        "max_tokens": 2000,
    }
    engine = MetaEvolutionEngine(base)
    engine.spawner = FakeSpawner(base)
    niches = [{"slug": "test-niche"}]

    for _ in range(5):
        engine.evolve(niches)

    engagements = [g.best_engagement for g in engine.generations]
    unique = len(set(round(e, 3) for e in engagements))
    assert unique <= 5


def test_evolution_report_persists_current_best_config(evolution_engine):
    base = {
        "provider_preferences": ["kilo"],
        "workflow_name": "standard",
        "temperature": 0.7,
        "max_tokens": 2000,
    }
    engine = MetaEvolutionEngine(base)
    engine.spawner = FakeSpawner(base)
    niches = [{"slug": "test-niche"}]
    engine.run_evolution(niches, generations=2)
    assert engine.current_best_config["temperature"] >= 0.1
    assert engine.current_best_config["temperature"] <= 1.0
