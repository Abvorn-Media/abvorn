"""SocialAmbassador — the warm, human face of Abvorn on every platform.

Knows the brand voice, respects the audience, never sounds like a bot.
Monitors the schedule, writes platform-native posts with personality,
posts via Composio, and keeps the Telegram channel warm and human.
Built with safety nets — one failure never blocks the rest."""

import asyncio, logging
from datetime import datetime
from .base import AgentBase
from ..deploy.social import SocialDeployer
from ..core import bus_progress

logger = logging.getLogger("abvorn.agents.ambassador")

# Monotonic "highest content.published id already promoted" marker.
_PROMOTED_WATERMARK = "ambassador_promoted_watermark"

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
        events = self._filter_new(events)
        mentions = self.bus.get_recent_events("social.mention", limit=5)
        schedule = self.state.get_meta("current_schedule", []) if self.state else []
        now = datetime.now().isoformat()
        due = [s for s in schedule if s.get("scheduled_at", "") <= now
               and not s.get("posted", False)]
        if not mentions:
            try:
                watcher_mentions = await asyncio.to_thread(
                    self.mention_watcher.poll
                )
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

    def _filter_new(self, events: list) -> list:
        # Watermark, not a truncated id set - see core/bus_progress.py. The old
        # 200-entry window against a thousands-deep backlog meant the same
        # published event was "fresh" again every cycle.
        return bus_progress.fresh_events(self.state, _PROMOTED_WATERMARK, events)

    def _mark_handled(self, event_ids):
        bus_progress.advance(self.state, _PROMOTED_WATERMARK, event_ids)

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
                    media = self._media_for(
                        p.get("niche", ""),
                        p.get("platform", ""),
                        p.get("url", ""),
                        title=p.get("headline", ""),
                    )
                    result = await self._craft_and_post(p, media_paths=media)
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
            msg = ev.get("message", {}) if isinstance(ev.get("message"), dict) else {}
            niche = msg.get("niche", ev.get("niche", "general"))
            url = msg.get("url", "") or ev.get("url", "")
            # Identity from the publisher: a niche slug alone cannot tell two
            # different reviews apart, so every tv post reused the same headline
            # and the same product card.
            title = msg.get("title", "") or ev.get("title", "")
            slug = msg.get("slug", "") or ev.get("slug", "")
            if not self.soul_check("promote_new_content", {"niche": niche}):
                return {"action": "soul_blocked", "decision": "promote_new_content"}
            result = await self._promote_niche(
                niche, url=url, title=title, slug=slug
            )
            self._mark_handled([ev["id"]])
            return result

        if decision == "engage":
            mentions = self._perception.get("mentions", [])
            if not mentions:
                return {"action": "none"}
            if not self.soul_check("engage_mentions", {"count": len(mentions)}):
                return {"action": "soul_blocked", "decision": "engage"}
            results = []
            for m in mentions[:5]:
                try:
                    reply = await asyncio.to_thread(
                        self.reply_generator.craft,
                        m,
                        {},
                    )
                    result = await asyncio.to_thread(
                        self.reply_poster.post,
                        m,
                        reply,
                    )
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
                        await asyncio.to_thread(
                            self.notifier.send,
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

    def _media_for(self, niche: str, platform: str, url: str = "", title: str = "") -> list[str]:
        """Build a real product card for the post about this niche.

        Until now the promote path called social.post() with no media at all,
        so LinkedIn always took the link-preview fallback and every post went
        out imageless. This reuses the composer the domination path already uses,
        which pulls the products straight off the published review page, so the
        card shows the actual product being written about rather than generic
        stock. Returns [] when the niche has no review page yet; the caller
        logs that rather than shipping a silent imageless post.
        """
        try:
            from ..domination.product_assets import load_products_for_niche, slug_from_url
            from ..domination.instagram_cards import compose_platform_media

            slug = slug_from_url(url) or niche
            products = load_products_for_niche(slug)
            if not products:
                logger.warning(
                    f"[Ambassador] no products resolved for {slug!r} — {platform} post will go out without a product image"
                )
                return []
            return compose_platform_media(
                products,
                niche=slug,
                title=title or f"{niche} guide",
                url=url,
                platform=platform,
            )
        except Exception as e:
            logger.warning(f"[Ambassador] media composition failed for {platform}: {e}")
            return []

    async def _craft_and_post(self, item: dict, media_paths: list[str] | None = None) -> dict:
        try:
            niche = item.get("niche", "general")
            platform = item.get("platform", "x")
            headline = item.get("headline", "")
            product = item.get("product", "")

            tone = PLATFORM_TONE.get(platform, "Be genuine and helpful with emojis.")
            wisdom = await asyncio.to_thread(
                self._get_platform_wisdom,
                platform,
            )
            prompt = (
                f"Write a social media post for {platform} about {product or niche}. "
                f"Headline idea: {headline}. {tone} "
                f"Include 1 question to prompt engagement. Use relevant emojis. {PERSONA}"
            )
            if wisdom:
                prompt += f"\n\nBrain insight: {wisdom}"

            try:
                post_text = await asyncio.to_thread(
                    self.router.ask,
                    prompt,
                    task="social",
                    system=PERSONA,
                )
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
                result = await asyncio.to_thread(
                    self.social.post,
                    content,
                    platform,
                    media_paths,
                )
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

    def _headline(self, niche: str, title: str = "", slug: str = "") -> str:
        """Announcement line for this specific article.

        The old form interpolated only the niche, so every promotion of a given
        niche rendered byte-identical text - "Just published our tv guide!" went
        out over and over with the same product card. Prefer the real article
        title from the publisher; fall back to the slug, humanised, so a niche
        announcement still reads as English instead of exposing a 60-char slug.
        """
        clean = " ".join(str(title or "").split()).strip().strip("\"'")
        if clean:
            return f"Just published: {clean}"
        raw = " ".join(str(slug or "").split()).strip()
        if raw:
            words = raw.replace("-", " ").replace("_", " ").strip()
            if words:
                return f"Just published our {words} guide!"
        return f"Just published our {niche} guide!"

    async def _promote_niche(self, niche: str, url: str = "",
                             title: str = "", slug: str = "") -> dict:
        logger.info(f"[Ambassador] Promoting new content: {niche}")
        platforms = ["x", "linkedin"]
        try:
            if self.social and getattr(self.social, 'composio', None):
                platforms.append("facebook")
        except Exception:
            pass
        headline = self._headline(niche, title, slug)
        logger.info(f"[Ambassador] headline: {headline!r}")
        results = []
        for platform in platforms:
            try:
                item = {"niche": niche, "platform": platform,
                        "headline": headline,
                        "product": slug or niche}
                # Same photo on every platform: one card, so the set reads as
                # one campaign instead of three unrelated posts.
                media = self._media_for(slug or niche, platform, url,
                                        title=headline)
                result = await self._craft_and_post(item, media_paths=media)
                result["media_count"] = len(media or [])
                results.append(result)
            except Exception as e:
                logger.warning(f"[Ambassador] {platform} promotion failed: {e}")
                results.append({"status": "failed", "platform": platform})
        return {"action": "promote", "niche": niche, "results": results}