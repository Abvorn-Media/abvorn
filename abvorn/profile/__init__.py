"""Profile management — brand-consistent social profiles."""

from .manager import ProfileManager, format_bio, format_display_name
from .schema import get_schema, list_schemas

__all__ = ["ProfileManager", "get_schema", "list_schemas", "format_bio", "format_display_name"]