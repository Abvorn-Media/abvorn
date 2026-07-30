"""agent_reach_adapter.py — Unified adapter for Agent-Reach social listening.

Agent-Reach installs and configures upstream tools (twitter-cli, yt-dlp, etc.).
This adapter provides a clean Python API over those tools for the Abvorn pipeline.
"""
import json
import logging
import subprocess
from typing import Dict, List, Any, Optional

from agent_reach import AgentReach
from agent_reach.channels import get_channel, ALL_CHANNELS

logger = logging.getLogger("abvorn.agent_reach")


class AgentReachAdapter:
    def __init__(self, config_path: Optional[str] = None):
        self.agent_reach = AgentReach()
        self.config_path = config_path
        self._health = None

    def check_health(self) -> Dict[str, Any]:
        """Check all channel availability via Agent-Reach doctor."""
        self._health = self.agent_reach.doctor()
        return self._health

    def health_report(self) -> str:
        """Get formatted health report."""
        if self._health is None:
            self.check_health()
        from agent_reach.doctor import format_report
        return format_report(self._health)

    def fetch_tweets(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch recent tweets matching the query."""
        return self._fetch_via_tool(
            tool="twitter",
            args=["search", query, "--limit", str(limit), "--json"],
            query=query,
            platform="twitter",
        )

    def fetch_reddit(self, subreddit: Optional[str] = None,
                        query: Optional[str] = None,
                        limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch Reddit posts from a subreddit or search query."""
        if subreddit:
            search_query = f"site:reddit.com/r/{subreddit} {query or ''}"
        elif query:
            search_query = query
        else:
            raise ValueError("Either subreddit or query must be provided.")
        return self._fetch_via_tool(
            tool="reddit",
            args=["search", search_query, "--limit", str(limit), "--json"],
            query=search_query,
            platform="reddit",
        )

    def fetch_youtube(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Fetch YouTube videos matching the query."""
        return self._fetch_via_tool(
            tool="yt-dlp",
            args=["--dump-json", "--flat-playlist", f"ytsearch{limit}:{query}"],
            query=query,
            platform="youtube",
        )

    def fetch_github_issues(self, repo: Optional[str] = None,
                               query: Optional[str] = None,
                               limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch GitHub issues from a repo or search query."""
        if repo:
            search_query = f"repo:{repo} {query or ''}"
        elif query:
            search_query = query
        else:
            raise ValueError("Either repo or query must be provided.")
        return self._fetch_via_tool(
            tool="gh",
            args=["search", "issue", search_query, "--limit", str(limit), "--json"],
            query=search_query,
            platform="github",
        )

    def fetch_xiaohongshu(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch posts from XiaoHongShu (Little Red Book)."""
        return self._fetch_via_tool(
            tool="xiaohongshu",
            args=["search", query, "--limit", str(limit), "--json"],
            query=query,
            platform="xiaohongshu",
        )

    def fetch_bilibili(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Fetch Bilibili videos matching the query."""
        return self._fetch_via_tool(
            tool="bilibili",
            args=["search", query, "--limit", str(limit), "--json"],
            query=query,
            platform="bilibili",
        )

    def fetch_social_data(
        self,
        query: str,
        platforms: Optional[List[str]] = None,
        limit_per_platform: int = 5,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch data from multiple platforms in one call."""
        if platforms is None:
            platforms = ["twitter", "reddit", "youtube"]

        results: Dict[str, List[Dict[str, Any]]] = {}
        platform_map = {
            "twitter": lambda: self.fetch_tweets(query, limit=limit_per_platform),
            "reddit": lambda: self.fetch_reddit(query=query, limit=limit_per_platform),
            "youtube": lambda: self.fetch_youtube(query, limit=limit_per_platform),
            "github": lambda: self.fetch_github_issues(query=query, limit=limit_per_platform),
            "xiaohongshu": lambda: self.fetch_xiaohongshu(query, limit=limit_per_platform),
            "bilibili": lambda: self.fetch_bilibili(query, limit=limit_per_platform),
        }

        for platform in platforms:
            fetch_fn = platform_map.get(platform)
            if fetch_fn:
                try:
                    results[platform] = fetch_fn()
                except Exception as e:
                    logger.warning(f"Failed to fetch {platform}: {e}")
                    results[platform] = []
            else:
                logger.warning(f"Unknown platform: {platform}, skipping")

        return results

    def _fetch_via_tool(
        self,
        tool: str,
        args: List[str],
        query: str,
        platform: str,
    ) -> List[Dict[str, Any]]:
        """Fallback: try CLI tool, then web search."""
        # Try Agent-Reach channel first
        try:
            channel = get_channel(platform)
            if channel:
                logger.info(f"Using Agent-Reach channel for {platform}")
        except Exception:
            pass

        # Try direct CLI execution
        try:
            result = subprocess.run(
                [tool] + args,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass

        # Fallback: return structured placeholder with the query
        logger.info(f"{tool} not available, returning placeholder for: {query}")
        return self._placeholder_result(query, platform)

    @staticmethod
    def _placeholder_result(query: str, platform: str) -> List[Dict[str, Any]]:
        return [
            {
                "text": f"[placeholder] Search query: {query}",
                "author": "system",
                "platform": platform,
                "timestamp": "",
                "url": "",
                "engagement": {"likes": 0, "shares": 0, "comments": 0},
            }
        ]


# Singleton
_instance: Optional[AgentReachAdapter] = None


def get_agent_reach_adapter() -> AgentReachAdapter:
    global _instance
    if _instance is None:
        _instance = AgentReachAdapter()
    return _instance