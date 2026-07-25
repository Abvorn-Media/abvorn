"""SiteRegistry — manages per-site identity config in state DB."""

import json
from .model import Site

STORAGE_KEY = "sites"


class SiteRegistry:
    """CRUD for Site objects. Stored as JSON in AbvornState meta."""

    def __init__(self, state):
        self._state = state

    def register(self, site: Site):
        sites = self._load_all()
        sites.append(site)
        self._save_all(sites)

    def get(self, site_id: str) -> Site | None:
        for s in self._load_all():
            if s.site_id == site_id:
                return s
        return None

    def find_by_niche(self, niche_slug: str) -> Site | None:
        for s in self._load_all():
            if niche_slug in s.niches:
                return s
        return None

    def assign_niche(self, site_id: str, niche_slug: str):
        sites = self._load_all()
        for s in sites:
            if s.site_id == site_id:
                if niche_slug not in s.niches:
                    s.niches.append(niche_slug)
                break
        self._save_all(sites)

    def auto_assign(self, niche_slug: str) -> Site | None:
        return self.find_by_niche(niche_slug)

    def list(self) -> list:
        return self._load_all()

    def count(self) -> int:
        return len(self._load_all())

    def _load_all(self) -> list:
        raw = self._state.get_meta(STORAGE_KEY, "[]")
        data = json.loads(raw) if isinstance(raw, str) else raw
        return [Site(**s) if not isinstance(s, Site) else s for s in data]

    def _save_all(self, sites: list):
        raw = json.dumps([s.__dict__ if hasattr(s, '__dict__') else s for s in sites], default=str)
        self._state.set_meta(STORAGE_KEY, raw)
