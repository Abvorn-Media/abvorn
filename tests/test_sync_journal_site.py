"""Tests for sync_journal_site's GitHub API publish path.

The local Windows journal task must publish through the API: git-over-HTTPS to
github.com times out on this host while api.github.com works, which is why the
task's mirror clone stopped pushing in September.
"""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock


def _load_module(tmp_path, monkeypatch):
    monkeypatch.setenv("ABVORN_SYNC_REPO_DIR", str(tmp_path))
    monkeypatch.setenv("ABVORN_SYNC_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SITE_URL", "https://abvorn.com")
    src = Path(__file__).resolve().parents[1] / "scripts" / "sync_journal_site.py"
    spec = importlib.util.spec_from_file_location("sync_journal_site_under_test", src)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_publish_via_api_commits_each_changed_file(tmp_path, monkeypatch):
    mod = _load_module(tmp_path, monkeypatch)

    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "evolution_journal.json").write_text('{"entries": []}', encoding="utf-8")
    (tmp_path / "docs" / "journal").mkdir(parents=True)
    (tmp_path / "docs" / "journal" / "index.html").write_text("<html>journal</html>", encoding="utf-8")

    commits = []

    class FakeDeployer:
        def __init__(self, token, repo):
            assert token == "fake-token"
            assert repo == "Abvorn-Media/abvorn"

        def _commit_file(self, repo, repo_path, content, message):
            commits.append((repo_path, content, message))
            return "sha"

    fake_repo = object()
    fake_gh = MagicMock()
    fake_gh.get_repo.return_value = fake_repo

    monkeypatch.setattr("abvorn.deploy.github.GitHubDeployer", FakeDeployer)
    monkeypatch.setattr("github.Github", lambda token: fake_gh)

    result = mod.publish_via_api(
        tmp_path,
        ["data/evolution_journal.json", "docs/journal/index.html"],
        "journal: sync live evolution entries",
        secrets={"GITHUB_TOKEN": "fake-token", "GITHUB_REPO": "Abvorn-Media/abvorn"},
    )

    assert result is True
    assert [c[0] for c in commits] == ["data/evolution_journal.json", "docs/journal/index.html"]
    assert commits[0][1] == '{"entries": []}'
    assert commits[1][1] == "<html>journal</html>"
    assert all(c[2] == "journal: sync live evolution entries" for c in commits)


def test_api_mode_skips_git_fetch_and_reset(tmp_path, monkeypatch):
    """git fetch to github.com times out on the local host, so API mode must
    not attempt it — otherwise the task dies before it can harvest anything."""
    mod = _load_module(tmp_path, monkeypatch)

    def fail_if_called(cmd, repo_dir, check=True):
        raise AssertionError(f"git must not run in API mode: {cmd}")

    monkeypatch.setattr(mod, "_git", fail_if_called)

    assert mod.prepare_repo(tmp_path, publish_api=True) is True


def test_git_mode_still_fetches_and_resets(tmp_path, monkeypatch):
    mod = _load_module(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        mod, "_git",
        lambda cmd, repo_dir, check=True: calls.append(cmd),
    )

    assert mod.prepare_repo(tmp_path, publish_api=False) is True
    assert calls[0][0] == "fetch"
    assert calls[1][0] == "reset"


def test_changed_journal_paths_maps_status_lines(tmp_path, monkeypatch):
    mod = _load_module(tmp_path, monkeypatch)
    status = (
        " M data/social_platforms.txt\n"
        " M data/evolution_journal.json\n"
        " M docs/journal/index.html\n"
        "?? scratch.json\n"
    )
    monkeypatch.setattr(
        mod, "_git", lambda cmd, repo_dir, check=True: type("R", (), {"stdout": status})()
    )

    assert mod.changed_journal_paths(tmp_path) == [
        "data/evolution_journal.json", "docs/journal/index.html"
    ]


def test_mirror_journal_skips_same_path(tmp_path, monkeypatch):
    """The local task uses one dir for repo and runtime data, so the mirror
    target is the source itself; copy2 on it raises WinError 32."""
    mod = _load_module(tmp_path, monkeypatch)
    journal = tmp_path / "evolution_journal.json"
    journal.write_text("{}", encoding="utf-8")

    copied = []
    monkeypatch.setattr(mod.shutil, "copy2", lambda src, dst: copied.append((src, dst)))

    assert mod.mirror_journal(journal, journal) is False
    assert copied == []
    assert mod.mirror_journal(journal, tmp_path / "other.json") is True
    assert len(copied) == 1


def test_publish_via_api_refuses_without_token(tmp_path, monkeypatch):
    mod = _load_module(tmp_path, monkeypatch)

    fake_deployer = MagicMock()
    monkeypatch.setattr("abvorn.deploy.github.GitHubDeployer", fake_deployer)
    monkeypatch.setattr("github.Github", MagicMock())

    result = mod.publish_via_api(
        tmp_path, ["data/evolution_journal.json"], "journal: sync", secrets={"GITHUB_TOKEN": ""}
    )

    assert result is False
    fake_deployer.assert_not_called()
