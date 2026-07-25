"""Tests for brand-aware deployment."""
from abvorn.sites.model import BrandConfig, DNAProfile
from abvorn.deploy.github import GitHubDeployer


def test_render_with_brand_config():
    from pathlib import Path
    import tempfile
    deployer = GitHubDeployer(token="fake", repo="user/repo")
    brand = BrandConfig(
        brand_name="Tech & Gadgets",
        brand_tagline="Honest reviews",
        logo_text="Tech & Gadgets",
        logo_icon="\U0001f50c",
        primary_color="#1a73e8",
        secondary_color="#34a853",
        dna_profile=DNAProfile.TECH,
        voice_rules={},
        domain="",
    )
    content = {
        "post_title": "Best TVs of 2026",
        "article_html": "<p>Test content</p>",
        "niche_slug": "best-tvs",
        "niche": "tv",
        "meta_description": "Test description",
        "tags": ["tv", "reviews"],
        "is_pick": True,
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        files = deployer.prepare_files(content, Path(tmpdir), brand=brand)
        assert len(files) == 1
        html = Path(files[0]).read_text(encoding="utf-8")
        assert "Tech" in html
        assert "#1a73e8" in html


def test_render_without_brand_uses_abvorn_defaults():
    from pathlib import Path
    import tempfile
    deployer = GitHubDeployer(token="fake", repo="user/repo")
    content = {"post_title": "Test", "article_html": "<p>Content</p>", "niche_slug": "test"}
    with tempfile.TemporaryDirectory() as tmpdir:
        files = deployer.prepare_files(content, Path(tmpdir))
        html = Path(files[0]).read_text(encoding="utf-8")
        assert "Abvorn" in html


def test_render_with_brand_has_dna_class():
    from pathlib import Path
    import tempfile
    deployer = GitHubDeployer("token", "owner/repo")
    brand = BrandConfig(
        brand_name="Clean Home",
        brand_tagline="Expert cleaning advice",
        logo_text="Clean Home",
        logo_icon="\U0001f3e0",
        primary_color="#41b3a3",
        secondary_color="#e8a87c",
        dna_profile=DNAProfile.WARM,
        voice_rules={},
        domain="",
    )
    content = {"post_title": "Best Vacuums", "article_html": "<p>Content</p>", "niche_slug": "best-vacuums"}
    with tempfile.TemporaryDirectory() as tmpdir:
        files = deployer.prepare_files(content, Path(tmpdir), brand=brand)
        html = Path(files[0]).read_text(encoding="utf-8")
        assert 'class="dna-warm"' in html

