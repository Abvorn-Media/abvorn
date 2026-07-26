"""SocialAmbassador — the warm, human face of Abvorn on every platform.

Knows the brand voice, respects the audience, never sounds like a bot.
Monitors the schedule, writes platform-native posts with personality,
posts via Composio, and keeps the Telegram channel warm and human.
Built with safety nets — one failure never blocks the rest."""

import logging
from datetime import datetime
from .base import AgentBase
from ..deploy.social import SocialDeployer

logger = logging.getLogger("abvorn.agents.ambassador")

PERSONA = (
    "You are Abvorn's social media ambassador — warm, knowledgeable, and genuinely helpful. "
    "You write like a real person who loves helping people make smart buying decisions. "
    "You never sound like a bot, never use hashtag spam, never overhype. "
    "You share real insights, ask real questions, and actually care about the audience. "
    "Your tone is friendly but expert — like a knowledgeable friend who did the research."
)

PLATFORM_TONE = {
    "x": "Concise and punchy. Ask a question or share a surprising insight in <280 chars. "
         "Use relevant emojis naturally — people engage more with visuals and personality. "
         "Share social proof ('our community found that...'). Build conversation, don't broadcast.",
    "linkedin": "Professional but warm. Share a lesson learned or a methodology. 2-3 short paragraphs. "
                "Use emojis sparingly but intentionally. Add value first, product mention second. "
                "Ask a real question to spark discussion in comments.",
    "facebook": "Conversational and community-focused. Write like you're talking to a friend. "
                "Ask for opinions. Use emojis freely. Build shared identity ('for those of us who...'). "
                "Share personal experience or a specific data point.",
}


class SocialAmbassador(AgentBase):
    """Posts to social media with warmth and personality. Safety-wrapped per-item."""

    def __init__(self, bus, state, router, social: SocialDeployer, brain=None, notifier=None, will=None, drive=None):
        super().__init__("SocialAmbassador", bus, state, brain, will, drive)
        self.router = router
        self.social = social
        self.notifier = notifier
        self._last_schedule_check = None
        self._perception = {}

        from ..engagement.watcher import MentionWatcher
        from ..engagement.replier import ReplyGenerator, ReplyPoster
        composio_key = getattr(social, 'composio_key', '') if social else ''
        self.mention_watcher = MentionWatcher(composio_key, state=state)
        self.reply_generator = ReplyGenerator(router=router)
        self.reply_poster = ReplyPoster(composio_key)

    def _get_platform_wisdom(self, platform: str) -> str:
        """Get platform-specific growth knowledge from brain principles."""
        if not self.brain:
            return ""
        try:
            return str(self.brain.query(f"social media growth tips for {platform}"))
        except Exception:
            return ""

    async def perceive(self) -> dict:
        events = self.bus.get_recent_events("content.published", limit=3)
        mentions = self.bus.get_recent_events("social.mention", limit=5)
        schedule = self.state.get_meta("current_schedule", []) if self.state else []
        now = datetime.now().isoformat()
        due = [s for s in schedule if s.get("scheduled_at", "") <= now
               and not s.get("posted", False)]
        if not mentions:
            try:
                watcher_mentions = self.mention_watcher.poll()
                if watcher_mentions:
                    mentions = watcher_mentions
            except Exception:
                pass
        p = {
            "published_content": events,
            "mentions": mentions,
            "schedule_due": due,
        }
        self._perception = p
        return p

    async def decide(self, perception: dict) -> str:
        if perception.get("schedule_due"):
            return "post_scheduled"
        if perception.get("published_content"):
            return "promote_new_content"
        if perception.get("mentions"):
            return "engage"
        return "wait"

    async def act(self, decision: str):
        if decision == "post_scheduled":
            posts = self._get_due_posts()
            results = []
            for p in posts[:3]:
                if not self.soul_check("post_scheduled", {"niche": p.get("niche", ""), "platform": p.get("platform", "")}):
                    results.append({"status": "soul_blocked", "platform": p.get("platform", "unknown")})
                    continue
                try:
                    result = await self._craft_and_post(p)
                    results.append(result)
                except Exception as e:
                    logger.warning(f"[Ambassador] post_scheduled item failed: {e}")
                    results.append({"status": "failed", "platform": p.get("platform", "unknown")})
            return {"action": "scheduled_posts", "results": results}

        if decision == "promote_new_content":
            events = self._perception.get("published_content", [])
            if not events:
                return {"action": "none"}
            ev = max(events, key=lambda e: e["created_at"])
            niche = ev.get("message", {}).get("niche", ev.get("niche", "general"))
            if not self.soul_check("promote_new_content", {"niche": niche}):
                return {"action": "soul_blocked", "decision": "promote_new_content"}
            return await self._promote_niche(niche)

        if decision == "engage":
            mentions = self._perception.get("mentions", [])
            if not mentions:
                return {"action": "none"}
            if not self.soul_check("engage_mentions", {"count": len(mentions)}):
                return {"action": "soul_blocked", "decision": "engage"}
            results = []
            for m in mentions[:5]:
                try:
                    reply = self.reply_generator.craft(m, {})
                    result = self.reply_poster.post(m, reply)
                    results.append(result)
                except Exception as e:
                    logger.warning(f"[Ambassador] Reply failed: {e}")
                    results.append({"status": "failed", "error": str(e)[:100]})
            return {"action": "engage", "replied": len(results)}

        return {"action": "none"}

    async def reflect(self, outcome):
        if outcome and outcome.get("results"):
            for r in outcome["results"]:
                if r.get("status") == "posted" and self.notifier:
                    platform = r.get("platform", "social")
                    try:
                        self.notifier.send(
                            f"✨ Just shared {r.get('title', 'something')} on {platform} — "
                            f"check it out and join the conversation!"
                        )
                    except Exception:
                        pass
        if self.drive:
            succeeded = bool(outcome and outcome.get("results") and any(r.get("status") == "posted" for r in outcome.get("results", [])))
            self.drive.log_outcome("social_cycle", succeeded=succeeded)

    def _get_due_posts(self) -> list[dict]:
        try:
            schedule = self.state.get_meta("current_schedule", []) if self.state else []
            now = datetime.now().isoformat()
            return [s for s in schedule if s.get("scheduled_at", "") <= now
                    and not s.get("posted", False)]
        except Exception:
            return []

    async def _craft_and_post(self, item: dict) -> dict:
        try:
            niche = item.get("niche", "general")
            platform = item.get("platform", "x")
            headline = item.get("headline", "")
            product = item.get("product", "")

            tone = PLATFORM_TONE.get(platform, "Be genuine and helpful with emojis.")
            wisdom = self._get_platform_wisdom(platform)
            prompt = (
                f"Write a social media post for {platform} about {product or niche}. "
                f"Headline idea: {headline}. {tone} "
                f"Include 1 question to prompt engagement. Use relevant emojis. {PERSONA}"
            )
            if wisdom:
                prompt += f"\n\nBrain insight: {wisdom}"

            try:
                post_text = self.router.ask(prompt, task="social", system=PERSONA)
            except Exception:
                post_text = f"Just published our latest guide on {niche}! Have you tried it yet? 🚀"

            if not post_text or len(post_text) < 10:
                post_text = f"Just published our latest guide on {niche}! Have you tried it yet? 🚀"

            content = {
                "post_title": headline or f"Guide: {niche}",
                "intro": post_text,
                "article_html": "",
                "meta_description": post_text[:160],
                "tags": [niche],
                "niche": niche,
            }

            try:
                result = self.social.post(content, platform)
            except Exception as e:
                logger.warning(f"[Ambassador] Social post failed: {e}")
                return {"status": "failed", "platform": platform, "error": str(e)[:100]}

            result["title"] = headline or post_text[:60]
            result["platform"] = platform

            if result.get("status") == "posted" and self.state:
                try:
                    schedule = self.state.get_meta("current_schedule", [])
                    for s in schedule:
                        if s.get("id") == item.get("id"):
                            s["posted"] = True
                            s["posted_at"] = datetime.now().isoformat()
                    self.state.set_meta("current_schedule", schedule)
                except Exception:
                    logger.warning("[Ambassador] Failed to update schedule state")

            return result
        except Exception as e:
            logger.error(f"[Ambassador] _craft_and_post failed: {e}")
            return {"status": "failed", "error": str(e)[:100], "platform": item.get("platform", "unknown")}

    async def _promote_niche(self, niche: str) -> dict:
        logger.info(f"[Ambassador] Promoting new content: {niche}")
        platforms = ["x", "linkedin"]
        try:
            if self.social and getattr(self.social, 'composio', None):
                platforms.append("facebook")
        except Exception:
            pass
        results = []
        for platform in platforms:
            try:
                item = {"niche": niche, "platform": platform,
                        "headline": f"Just published our {niche} guide!",
                        "product": niche}
                result = await self._craft_and_post(item)
                results.append(result)
            except Exception as e:
                logger.warning(f"[Ambassador] {platform} promotion failed: {e}")
                results.append({"status": "failed", "platform": platform})
        return {"action": "promote", "niche": niche, "results": results}