"""Platform registry — plugin system for all content platforms.

Adding a new platform:
1. Write an adapter function in adapters.py with @register("name")
2. Write a deployer class in deployers.py (optional)
3. That's it. No other file needs to change.
"""

from .registry import PlatformRegistry, PlatformConfig

registry = PlatformRegistry()

__all__ = ["registry", "PlatformConfig"]