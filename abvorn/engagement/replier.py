"""ReplyGenerator and ReplyPoster — craft warm replies and post them via Composio."""

import logging
from datetime import datetime

logger = logging.getLogger("abvorn.engagement.replier")

ENGAGEMENT_PERSONA = (
    "You are Abvorn's social media ambassador — warm, knowledgeable, and genuinely helpful. "
    "Someone just mentioned Abvorn or asked a question on social media. Reply in a way that feels "
    "human, not corporate. Use relevant emojis naturally — people engage more with them. "
    "Be specific, be helpful, and never sound like a bot. "
    "Reference the community when relevant ('our community found that...'). "
    "Build shared identity ('for people like us who care about...'). "
    "Stay warm and consistent with the Abvorn brand voice."
)

try:
    from composio import ComposioToolSet, Action
    HAS_COMPOSIO = True
except ImportError:
    HAS_COMPOSIO = False
    Action = object


class ReplyGenerator:
    """Crafts warm, on-brand replies to social mentions."""

    def __init__(self, router=None):
        self.router = router

    def craft(self, mention: dict, context: dict = None) -> str:
        """Generate a reply to a mention."""
        context = context or {}
        if self.router:
            try:
                prompt = (
                    f"The user @{mention.get('author', 'unknown')} said: "
                    f"\"{mention.get('text', '')}\"\n\n"
                    f"Context: we just posted about {context.get('niche', 'products')} — "
                    f"\"{context.get('post_title', 'our latest guide')}\".\n\n"
                    f"Write a warm, helpful reply (1-3 sentences) with relevant emojis:"
                )
                reply = self.router.ask(prompt, task="social", system=ENGAGEMENT_PERSONA)
                if reply and len(reply) > 10:
                    return reply.strip()
            except Exception as e:
                logger.warning(f"Reply generation failed: {e}")

        return f"Thanks for the question, @{mention.get('author', 'unknown')}! 👍 " \
               f"Great point — we cover exactly that in our guide. Hope it helps!"


class ReplyPoster:
    """Posts replies to social media via Composio."""

    def __init__(self, composio_key: str = ""):
        self.composio_key = composio_key
        self._composio = None
        if composio_key and HAS_COMPOSIO:
            try:
                self._composio = ComposioToolSet(api_key=composio_key)
            except Exception as e:
                logger.warning(f"Composio init failed: {e}")

    def post(self, mention: dict, reply_text: str) -> dict:
        """Post a reply to the mention's tweet."""
        # MASTER SWITCH: no live replies until explicitly enabled.
        from ..core.social_gate import require_social_publishing
        if not require_social_publishing():
            logger.info("Reply staged (not posted) — publish gate OFF")
            return {"status": "staged", "mention_id": mention.get("id", ""),
                    "author": mention.get("author", ""), "text": reply_text[:280]}
        # Platform scoping: with the gate ON, only explicitly allowed platforms reply.
        from ..deploy.social import _allowed_platforms
        allowed = _allowed_platforms()
        source = str(mention.get("platform", "") or "").lower() or "x"
        if allowed is not None and source not in allowed:
            logger.info(f"Reply staged (not posted) — {source} not in allowed list")
            return {"status": "staged", "mention_id": mention.get("id", ""),
                    "author": mention.get("author", ""), "text": reply_text[:280]}
        if not self._composio:
            return {"status": "skipped", "reason": "no_composio"}
        tweet_id = mention.get("tweet_id", "")
        if not tweet_id:
            return {"status": "error", "reason": "no_tweet_id"}
        reply_action = getattr(Action, "TWITTER_CREATE_TWEET", None)
        if not reply_action:
            return {"status": "error", "reason": "no_action"}
        try:
            self._composio.execute_action(reply_action, params={
                "text": reply_text[:280],
                "reply_to": tweet_id,
            })
            logger.info(f"Replied to {mention.get('author')}: {reply_text[:60]}...")
            return {"status": "posted", "mention_id": mention.get("id", ""),
                    "author": mention.get("author", "")}
        except Exception as e:
            logger.warning(f"Reply failed: {e}")
            return {"status": "failed", "error": str(e)[:100]}