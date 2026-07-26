"""Central platform registry — plugins register here, consumers query here."""

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger("abvorn.platform.registry")


@dataclass
class PlatformConfig:
    """Configuration for a single platform."""
    name: str
    label: str
    adapter_fn: Callable
    deployer_cls: Optional[type] = None
    content_types: list[str] = field(default_factory=lambda: ["thread", "post", "article", "script", "carousel", "pin"])
    max_length: int = 0
    supports_html: bool = False
    supports_media: bool = False
    schedule_profile: Optional[dict] = None
    category: str = "social"
    is_export_only: bool = False
    voice_profile: Optional[dict] = None        # Per-platform voice rules


class PlatformRegistry:
    """Plugin registry for content platforms. Platforms register themselves."""

    def __init__(self):
        self._platforms: dict[str, PlatformConfig] = {}

    def register(self, name: str, label: str = "", adapter_fn=None,
                 deployer_cls=None, content_types=None,
                 max_length: int = 0, supports_html: bool = False,
                 supports_media: bool = False, schedule_profile: dict = None,
                 category: str = "social", is_export_only: bool = False,
                 voice_profile: dict = None):
        """Register a platform. Can be used as a decorator on adapter functions."""
        def _register(fn):
            nonlocal adapter_fn
            adapter_fn = fn
            config = PlatformConfig(
                name=name, label=label or name.title(),
                adapter_fn=adapter_fn, deployer_cls=deployer_cls,
                content_types=content_types or ["post"],
                max_length=max_length, supports_html=supports_html,
                supports_media=supports_media,
                schedule_profile=schedule_profile,
                category=category, is_export_only=is_export_only,
                voice_profile=voice_profile,
            )
            self._platforms[name] = config
            logger.debug(f"Platform registered: {name}")
            return fn

        if adapter_fn is not None:
            return _register(adapter_fn)
        return _register

    def get(self, name: str) -> PlatformConfig:
        if name not in self._platforms:
            raise ValueError(f"Unknown platform: '{name}'. Available: {', '.join(self.list())}")
        return self._platforms[name]

    def list(self, category: str = None) -> list[str]:
        if category:
            return [n for n, p in self._platforms.items() if p.category == category]
        return list(self._platforms.keys())

    def list_with_labels(self) -> list[dict]:
        return [{"name": n, "label": p.label, "category": p.category} for n, p in self._platforms.items()]

    def has(self, name: str) -> bool:
        return name in self._platforms

    def adapter(self, name: str) -> Callable:
        return self.get(name).adapter_fn

    def deployer(self, name: str) -> Optional[type]:
        return self.get(name).deployer_cls

    def schedule_profile(self, name: str) -> Optional[dict]:
        return self.get(name).schedule_profile

    def voice_profile(self, name: str) -> Optional[dict]:
        return self.get(name).voice_profile

    def count(self) -> int:
        return len(self._platforms)