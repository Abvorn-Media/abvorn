"""agent_reach_adapter.py — Real-time social data fetcher using Agent-Reach internal APIs.

Agent-Reach installs and configures upstream tools (twitter-cli, yt-dlp, etc.).
This adapter provides a clean Python API over those tools for the Abvorn pipeline.
"""
import logging
from typing import List, Dict, Any, Optional

try:
    from agent_reach import twitter, reddit, youtube, github, xiaohongshu, bilibili
except ImportError:
    twitter = reddit = youtube = github = xiaohongshu = bilibili = None
    logging.warning("Agent-Reach not installed; social data will be unavailable.")

logger = logging.getLogger(__name__)


class AgentReachAdapter:
    def __init__(self):
        self._available = False
        self._check_available()

    def _check_available(self):
        if twitter is None:
            logger.warning("Agent-Reach not installed; social data will be unavailable.")
            self._available = False
            return
        self._available = True

    @property
    def available(self) -> bool:
        return self._available

    def fetch_tweets(self, query: str, limit: int = 10) -> List[Dict]:
        """Fetch recent tweets matching query."""
        if not self._available:
            return []
        try:
            results = twitter.search(query, limit=limit)
            return [{
                'text': r.get('text', ''),
                'author': r.get('author', {}).get('username', 'unknown'),
                'timestamp': r.get('created_at'),
                'url': r.get('url'),
                'engagement': {
                    'likes': r.get('like_count', 0),
                    'retweets': r.get('retweet_count', 0),
                    'replies': r.get('reply_count', 0),
                },
            } for r in results]
        except Exception as e:
            logger.error(f"Twitter fetch failed: {e}")
            return []

    def fetch_reddit_posts(self, subreddit: Optional[str] = None,
                           query: Optional[str] = None,
                           limit: int = 5) -> List[Dict]:
        """Fetch Reddit posts from subreddit or search."""
        if not self._available:
            return []
        try:
            if subreddit:
                results = reddit.subreddit(subreddit).hot(limit=limit)
            elif query:
                results = reddit.search(query, limit=limit)
            else:
                return []
            return [{
                'text': r.title + '\n' + (r.selftext or ''),
                'author': str(r.author),
                'timestamp': r.created_utc,
                'url': r.url,
                'engagement': {
                    'upvotes': r.score,
                    'comments': r.num_comments,
                },
            } for r in results]
        except Exception as e:
            logger.error(f"Reddit fetch failed: {e}")
            return []

    def fetch_youtube_videos(self, query: str, limit: int = 3) -> List[Dict]:
        """Fetch YouTube videos matching query."""
        if not self._available:
            return []
        try:
            results = youtube.search(query, limit=limit)
            return [{
                'text': r.get('title', '') + '\n' + r.get('description', ''),
                'author': r.get('channel_name', ''),
                'timestamp': r.get('published_at'),
                'url': f"https://youtu.be/{r.get('video_id')}",
                'engagement': {
                    'views': r.get('view_count', 0),
                    'likes': r.get('like_count', 0),
                    'comments': r.get('comment_count', 0),
                },
            } for r in results]
        except Exception as e:
            logger.error(f"YouTube fetch failed: {e}")
            return []

    def fetch_github_issues(self, repo: str, query: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """Fetch GitHub issues from repo or search query."""
        if not self._available:
            return []
        try:
            results = github.issues(repo, query=query, limit=limit)
            return [{
                'text': r.get('title', '') + '\n' + r.get('body', ''),
                'author': r.get('user', {}).get('login', ''),
                'timestamp': r.get('created_at'),
                'url': r.get('html_url'),
                'engagement': {
                    'comments': r.get('comments', 0),
                    'reactions': len(r.get('reactions', {})),
                },
            } for r in results]
        except Exception as e:
            logger.error(f"GitHub fetch failed: {e}")
            return []

    def fetch_social_data(self, query: str,
                          platforms: List[str] = ['twitter', 'reddit', 'youtube'],
                          limit_per_platform: int = 5) -> Dict[str, List[Dict]]:
        """Aggregate data from multiple platforms."""
        if not self._available:
            logger.warning("Agent-Reach not available; returning empty social data")
            return {}
        data: Dict[str, List[Dict]] = {}
        if 'twitter' in platforms:
            data['twitter'] = self.fetch_tweets(query, limit=limit_per_platform)
        if 'reddit' in platforms:
            data['reddit'] = self.fetch_reddit_posts(query=query, limit=limit_per_platform)
        if 'youtube' in platforms:
            data['youtube'] = self.fetch_youtube_videos(query, limit=limit_per_platform)
        return data


_instance: Optional[AgentReachAdapter] = None


def get_agent_reach_adapter() -> AgentReachAdapter:
    global _instance
    if _instance is None:
        _instance = AgentReachAdapter()
    return _instance