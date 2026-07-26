"""BootstrapMigration — creates initial site + redirects for existing content."""

import logging
from datetime import datetime
from .model import Site
from .registry import SiteRegistry
from ..deploy.redirect import generate_redirect_html

logger = logging.getLogger("abvorn.sites.migration")


class BootstrapMigration:
    """Creates initial site if none exist, assigns existing niches, writes redirects."""

    SITE_ID = "tech-gadgets-main"
    SLUG = "tech-gadgets"
    NAME = "Tech & Gadgets"
    TAGLINE = "Expert reviews for smart shoppers"
    NICHE_PREFIXES = ["tv", "laptop", "monitor"]

    def __init__(self, state, deployer):
        self._registry = SiteRegistry(state)
        self._deployer = deployer

    def needs_migration(self) -> bool:
        return self._registry.count() == 0

    def run(self) -> list[str]:
        results = []
        if not self.needs_migration():
            results.append("Sites already exist — skipping bootstrap")
            return results

        site = Site(
            site_id=self.SITE_ID,
            slug=self.SLUG,
            name=self.NAME,
            tagline=self.TAGLINE,
            logo_text=self.NAME,
            logo_icon="\U0001f50c",
            primary_color="#1a73e8",
            secondary_color="#34a853",
            voice_rules={},
            niches=list(self.NICHE_PREFIXES),
            domain="",
            status="active",
            created_at=datetime.now().isoformat(),
        )
        self._registry.register(site)
        results.append(f"Created site '{self.NAME}' ({self.SLUG})")

        for niche in self.NICHE_PREFIXES:
            redirect_html = generate_redirect_html(f"/{self.SLUG}/{niche}/")
            self._deployer.deploy_html(redirect_html, f"{niche}/index.html")
            results.append(f"Wrote redirect: docs/{niche}/ \u2192 /{self.SLUG}/{niche}/")

        return results
