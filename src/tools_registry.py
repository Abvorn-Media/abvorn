import logging
import inspect
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tools_registry")


class ToolAccess(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    ADMIN = "admin"


@dataclass
class Tool:
    name: str
    description: str
    function: Callable
    access_level: ToolAccess = ToolAccess.PUBLIC
    parameters: Dict[str, Any] = field(default_factory=dict)
    retries: int = 2
    timeout: int = 30
    rate_limit: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.usage_history: List[Dict[str, Any]] = []
        self._rate_limit_counts: Dict[str, int] = {}
        self._last_reset: Dict[str, float] = {}

    def register(self, name: str, description: str, function: Callable,
                 access_level: ToolAccess = ToolAccess.PUBLIC,
                 parameters: Dict[str, Any] = None,
                 retries: int = 2, timeout: int = 30,
                 rate_limit: Optional[int] = None) -> None:
        tool = Tool(
            name=name,
            description=description,
            function=function,
            access_level=access_level,
            parameters=parameters or self._infer_parameters(function),
            retries=retries,
            timeout=timeout,
            rate_limit=rate_limit,
        )
        self.tools[name] = tool
        logger.info(f"Tool registered: {name}")

    def _infer_parameters(self, func: Callable) -> Dict[str, Any]:
        sig = inspect.signature(func)
        params = {}
        for name, param in sig.parameters.items():
            params[name] = {
                "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "Any",
                "default": param.default if param.default != inspect.Parameter.empty else None,
            }
        return params

    def get_tool(self, name: str) -> Optional[Tool]:
        return self.tools.get(name)

    def list_tools(self, access_level: ToolAccess = None) -> List[Tool]:
        if access_level:
            return [t for t in self.tools.values() if t.access_level == access_level]
        return list(self.tools.values())

    def search_tools(self, query: str) -> List[Tool]:
        query_lower = query.lower()
        return [t for t in self.tools.values()
                if query_lower in t.name.lower() or query_lower in t.description.lower()]

    def execute(self, tool_name: str, **kwargs) -> Any:
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found")
        if tool.rate_limit:
            if not self._check_rate_limit(tool_name, tool.rate_limit):
                raise Exception(f"Rate limit exceeded for tool '{tool_name}'")
        result = tool.function(**kwargs)
        self.usage_history.append({
            "tool": tool_name,
            "timestamp": datetime.now().isoformat(),
            "success": True,
        })
        return result

    def _check_rate_limit(self, tool_name: str, limit: int) -> bool:
        import time
        now = time.time()
        if tool_name not in self._last_reset:
            self._last_reset[tool_name] = now
            self._rate_limit_counts[tool_name] = 0
            return True
        if now - self._last_reset[tool_name] > 60:
            self._last_reset[tool_name] = now
            self._rate_limit_counts[tool_name] = 0
        self._rate_limit_counts[tool_name] += 1
        return self._rate_limit_counts[tool_name] <= limit

    def generate_report(self) -> Dict[str, Any]:
        return {
            "total_tools": len(self.tools),
            "tools_by_access": {
                level.value: len([t for t in self.tools.values() if t.access_level == level])
                for level in ToolAccess
            },
            "usage_count": len(self.usage_history),
            "tools": [{"name": t.name, "description": t.description} for t in self.tools.values()],
            "recent_usage": self.usage_history[-20:],
        }


def create_tool_registry() -> ToolRegistry:
    return ToolRegistry()
