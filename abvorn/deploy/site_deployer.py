"""SiteAwareDeployer — wraps GitHubDeployer with per-site brand resolution."""

import logging
from ..sites.registry import SiteRegistry
from ..sites.brand import get_brand

logger = logging.getLogger("abvorn.deploy.site_deployer")


class SiteAwareDeployer:
    """Delegates to GitHubDeployer, enriching output with per-site brand config."""

    def __init__(self, inner_deployer, state):
        self._inner = inner_deployer
        self._registry = SiteRegistry(state)

    def deploy_niche(self, niche_slug: str, content: dict, persona: dict | None = None) -> bool:
        site = self._registry.find_by_niche(niche_slug)
        if not site:
            logger.warning(f"No site found for niche '{niche_slug}'")
            return False

        brand = get_brand(site, persona)
        output_path = f"{site.slug}/{niche_slug}"
        html = self._inner.render_page(
            title=content.get("title", ""),
            content=content.get("content", ""),
            slug=content.get("slug", niche_slug),
            brand=brand,
        )
        try:
            self._inner.deploy_html(html, output_path)
            return True
        except Exception as e:
            logger.error(f"Deploy failed for {niche_slug}: {e}")
            return False
