"""Guard the live-social platform allow-list.

The publish gate in abvorn.deploy.social._allowed_platforms() is the single
source of truth for BOTH publish paths (SocialDeployer and the domination
SocialPublisher). A platform missing from data/social_platforms.txt is staged
or exported forever — it never goes live, no matter how healthy its
credentials or Composio connection are. This test catches that silent failure.
"""

from pathlib import Path

from abvorn.deploy.social import _allowed_platforms


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_LIVE_PLATFORMS = {"telegram", "linkedin", "pinterest", "instagram"}


def test_all_core_platforms_are_allowed_to_go_live(monkeypatch):
    """Every core social must be in the publish allow-list, not just staged."""
    monkeypatch.delenv("ABVORN_SOCIAL_PLATFORMS", raising=False)
    monkeypatch.chdir(REPO_ROOT)

    allowed = _allowed_platforms()

    assert allowed is not None, "publish allow-list must not be empty/unset"
    missing = EXPECTED_LIVE_PLATFORMS - allowed
    assert not missing, (
        f"platforms missing from data/social_platforms.txt (never published): "
        f"{sorted(missing)}; found {sorted(allowed)}"
    )
