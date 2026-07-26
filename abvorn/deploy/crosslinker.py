"""CrossLinker — injects contextual cross-site links into posts."""

import logging
from ..sites.registry import SiteRegistry

logger = logging.getLogger("abvorn.deploy.crosslinker")
MAX_LINKS = 2


class CrossLinker:
    """Adds sister-site contextual links after content generation."""

    def __init__(self, state):
        self._registry = SiteRegistry(state)

    def inject_links(self, html_content: str, niche_slug: str) -> str:
        try:
            site = self._registry.find_by_niche(niche_slug)
            if not site:
                return html_content

            sister_sites = [s for s in self._registry.list() if s.site_id != site.site_id]
            if not sister_sites:
                return html_content

            links_added = 0
            for sister in sister_sites:
                if links_added >= MAX_LINKS:
                    break
                for sister_niche in sister.niches:
                    if links_added >= MAX_LINKS:
                        break
                    link_text = f"Check out our guide to <a href='/{sister.slug}/{sister_niche}/'>{sister_niche.replace('-', ' ').title()}</a>"
                    html_content += f"\n<p>{link_text}</p>"
                    links_added += 1
            return html_content
        except Exception as e:
            logger.debug(f"CrossLinker failed: {e}")
            return html_content
