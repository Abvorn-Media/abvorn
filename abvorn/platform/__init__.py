"""Platform registry — plugin system for all content platforms.

Adding a new platform:
1. Write an adapter function in adapters.py with @register("name")
2. Write a deployer class in deployers.py (optional)
3. That's it. No other file needs to change.
"""

from .registry import PlatformRegistry, PlatformConfig

registry = PlatformRegistry()

# Import adapters so platforms self-register. Consumers (schedule, sender,
# deploy) rely on the registry being populated on import — never import the
# package without this.
from . import adapters  # noqa: E402,F401

__all__ = ["registry", "PlatformConfig"]