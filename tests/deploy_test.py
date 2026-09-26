"""Tests for brand-aware deployment."""
import pytest
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


"""Tests for SiteAwareDeployer."""
from unittest.mock import MagicMock, patch
from abvorn.deploy.site_deployer import SiteAwareDeployer
from abvorn.sites.model import Site


def test_site_aware_deployer_looks_up_site():
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"site_id":"s1","slug":"tech-gadgets","name":"Tech & Gadgets",'
        '"tagline":"","logo_text":"TG","logo_icon":"T","primary_color":"#000",'
        '"secondary_color":"#fff","voice_rules":{},"niches":["tv"],'
        '"domain":"","status":"active","created_at":""}]'
    )
    inner = MagicMock()
    inner.render_page.return_value = "<html></html>"
    deployer = SiteAwareDeployer(inner, state)
    deployer.deploy_niche("tv", {"title":"Test","content":"<p>Test</p>"})
    assert inner.render_page.called

def test_site_aware_deployer_no_site_found():
    state = MagicMock()
    state.get_meta.return_value = "[]"
    inner = MagicMock()
    deployer = SiteAwareDeployer(inner, state)
    result = deployer.deploy_niche("unknown", {"title":"Test","content":"<p>Test</p>"})
    assert result is False


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


def test_page_includes_persuasion_when_brand_and_state():
    from pathlib import Path
    import tempfile
    from unittest.mock import MagicMock
    from abvorn.sites.model import BrandConfig, DNAProfile
    deployer = GitHubDeployer(token="fake", repo="user/repo")
    brand = BrandConfig(brand_name="Test", brand_tagline="", logo_text="T", logo_icon="T",
                        primary_color="#000", secondary_color="#fff",
                        dna_profile=DNAProfile.TECH, voice_rules={}, domain="")
    state = MagicMock()
    state.get_meta.return_value = (
        '[{"name":"Sony WH-1000XM5","tagline":"Best ANC","price_range":"$349",'
        '"affiliate_url":"https://amzn.to/sony","reason_to_buy":"Quietest on market"}]'
    )
    content = {"post_title": "Best TVs", "article_html": "<p>Content</p>", "niche_slug": "best-tvs",
               "niche": "tv"}
    with tempfile.TemporaryDirectory() as tmpdir:
        files = deployer.prepare_files(content, Path(tmpdir), brand=brand, state=state)
        html = Path(files[0]).read_text(encoding="utf-8")
        assert "abvorn-persuasion" in html, "Persuasion widget not found in output"
        assert "Sony" in html, "Product name not found in widget"


def test_deploy_html_blocks_placeholder_content():
    """Placeholder pages ('coming soon') must never be pushed, regardless of caller."""
    deployer = GitHubDeployer(token="fake", repo="user/repo")
    result = deployer.deploy_html("<html>Categories coming soon</html>", "index.html")
    assert result["status"] == "error"
    assert "placeholder" in result["message"]


def test_deploy_html_blocks_category_placeholder():
    deployer = GitHubDeployer(token="fake", repo="user/repo")
    result = deployer.deploy_html("<html>Reviews for this category are being researched</html>", "fitness/index.html")
    assert result["status"] == "error"


def test_deploy_html_allows_real_content():
    deployer = GitHubDeployer(token="fake", repo="user/repo")
    result = deployer.deploy_html("<html>Abvorn — real reviews here</html>", "index.html")
    # Without a real token the GitHub call fails, but it must NOT be blocked as a placeholder.
    assert result["status"] != "placeholder blocked"
    assert result.get("message") != "placeholder content blocked"


# --- ref-edit race ---------------------------------------------------------
# A deploy reads the branch head, builds a commit on it, then edits the ref.
# Anything that pushes in between (a local `git push`, or the other deploy
# path) makes that edit a non-fast-forward and the deploy is lost. The daemon
# hit exactly this: "deploy_html failed for tv/index.html: Update is not a fast
# forward: 422".


class _FakeGithubError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(f"{message}: {status} " + '{"status": "%d"}' % status)


class _FakeRef:
    def __init__(self, repo):
        self._repo = repo
        self.object = type("Obj", (), {})()
        self.object.sha = repo.head

    def edit(self, sha):
        self._repo.edit_attempts.append(self.object.sha)
        if self._repo.fail_edits >= len(self._repo.edit_attempts):
            if self._repo.advance_on_failure:
                self._repo.head = f"head{len(self._repo.edit_attempts)}"
            raise _FakeGithubError(self._repo.fail_status, self._repo.fail_message)
        self.object.sha = sha


class _FakeRepo:
    def __init__(self, fail_edits=1, fail_status=422,
                 fail_message="Update is not a fast forward", advance_on_failure=True):
        self.head = "base0"
        self.fail_edits = fail_edits
        self.fail_status = fail_status
        self.fail_message = fail_message
        self.advance_on_failure = advance_on_failure
        self.edit_attempts = []
        self.parents = []

    def get_git_ref(self, name):
        assert name == "heads/main", name
        return _FakeRef(self)

    def get_git_tree(self, sha):
        return f"tree-of-{sha}"

    def create_git_blob(self, content, encoding):
        return type("Blob", (), {"sha": "blob1"})()

    def create_git_tree(self, elements, base_tree):
        return f"newtree-from-{base_tree}"

    def get_git_commit(self, sha):
        return f"commit-{sha}"

    def create_git_commit(self, message, tree, parents):
        self.parents.append((message, tuple(parents)))
        return type("Commit", (), {"sha": f"newcommit{len(self.parents)}"})()


@pytest.fixture(autouse=True)
def _no_backoff_sleep(monkeypatch):
    """The retry backoff is wall-clock; keep the tests instant."""
    monkeypatch.setattr("abvorn.deploy.github.time.sleep", lambda *_: None)


def test_is_non_fast_forward_matches_only_the_ref_race():
    from abvorn.deploy.github import _is_non_fast_forward
    assert _is_non_fast_forward(_FakeGithubError(422, "Update is not a fast forward"))
    # 422 is also used for real validation errors, which must not be retried.
    assert not _is_non_fast_forward(_FakeGithubError(422, "Invalid request"))
    assert not _is_non_fast_forward(_FakeGithubError(500, "Update is not a fast forward"))
    assert not _is_non_fast_forward(RuntimeError("boom"))


def test_commit_file_retries_when_the_branch_moves(monkeypatch):
    """The exact daemon failure: a competing writer lands between the head
    read and the ref edit, and the deploy still lands."""
    deployer = GitHubDeployer(token="fake", repo="user/repo")
    repo = _FakeRepo(fail_edits=1)

    sha = deployer._commit_file(repo, "docs/x/index.html", "<html>hi</html>", "deploy: x/index.html")

    assert len(repo.edit_attempts) == 2, "should have retried exactly once"
    assert sha == "newcommit2"
    # The retry must parent on the *new* head, not replay the stale base.
    assert repo.parents[0][1] == ("commit-base0",)
    assert repo.parents[1][1] == ("commit-head1",), "retry did not rebuild on the fresh head"


def test_commit_file_succeeds_first_try_without_a_race():
    deployer = GitHubDeployer(token="fake", repo="user/repo")
    repo = _FakeRepo(fail_edits=0)
    sha = deployer._commit_file(repo, "docs/x/index.html", "<html>hi</html>", "deploy: x/index.html")
    assert sha == "newcommit1"
    assert repo.edit_attempts == ["base0"]


def test_commit_file_gives_up_after_bounded_retries():
    """A branch that keeps moving must not spin forever."""
    deployer = GitHubDeployer(token="fake", repo="user/repo")
    repo = _FakeRepo(fail_edits=99)

    with pytest.raises(_FakeGithubError):
        deployer._commit_file(repo, "docs/x/index.html", "<html>hi</html>", "deploy: x/index.html", attempts=3)
    assert len(repo.edit_attempts) == 3


def test_commit_file_does_not_retry_other_errors():
    deployer = GitHubDeployer(token="fake", repo="user/repo")
    repo = _FakeRepo(fail_edits=99, fail_status=500, fail_message="Server Error")

    with pytest.raises(_FakeGithubError):
        deployer._commit_file(repo, "docs/x/index.html", "<html>hi</html>", "deploy: x/index.html")
    assert len(repo.edit_attempts) == 1, "a 500 is not a lost race, retrying just wastes the quota"

