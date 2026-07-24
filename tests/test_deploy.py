import pytest, tempfile, json
from pathlib import Path
from abvorn.deploy.github import GitHubDeployer

def test_prepare_deploy():
    """Should prepare files for deployment without pushing."""
    deployer = GitHubDeployer(token="fake", repo="user/repo")
    content = {
        "post_title": "Test Post",
        "article_html": "<p>Test</p>",
        "niche_slug": "test-niche",
        "products": [{"name": "Product A"}],
        "tags": ["test"],
    }
    with tempfile.TemporaryDirectory() as tmp:
        files = deployer.prepare_files(content, Path(tmp))
        assert len(files) > 0
        for f in files:
            assert Path(f).exists()