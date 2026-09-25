"""Domination Orchestrator — The Brain of the social domination engine.

Orchestrates the full pipeline:
1. Content Intelligence → parse RSS, score virality
2. Viral Script Generator → platform-native scripts with hooks
3. Pexels Asset Fetcher → images/videos for each post
4. Cinematic Filter → brand overlays on images
5. Audio System → voiceover scripts
6. Social Publisher → Composio publish or export
7. Self-Learning Engine → record + optimize

Designed to run as a scheduled task within the Abvorn daemon.
"""

import logging
import os
from datetime import datetime

from .content_intelligence import ContentIntelligence
from .viral_script_generator import ViralScriptGenerator
from .pexels_asset_fetcher import PexelsAssetFetcher
from .cinematic_filter import CinematicFilter
from .audio_system import AudioSystem
from .self_learning_engine import SelfLearningEngine, normalize_source_url
from .social_publisher import SocialPublisher
from .budget import APIBudget

logger = logging.getLogger("abvorn.domination.orchestrator")


class DominationOrchestrator:
    """Full-stack social domination engine — RSS → platform-native content → published."""

    def __init__(
        self,
        rss_url: str = "",
        rss_path: str = "",
        pexels_key: str = "",
        composio_key: str = "",
        db_path: str = "",
        budget=None,
        persona_engine=None,
        persona_registry=None,
    ):
        self.budget = budget or APIBudget()
        self.content_intel = ContentIntelligence(rss_url=rss_url, rss_path=rss_path)
        self.script_gen = ViralScriptGenerator()
        self.pexels = PexelsAssetFetcher(api_key=pexels_key, budget=self.budget)
        self.cinematic = CinematicFilter()
        self.audio = AudioSystem()
        self.learner = SelfLearningEngine(db_path=db_path)
        self.publisher = SocialPublisher(composio_key=composio_key)
        self.persona_engine = persona_engine
        self.persona_registry = persona_registry

        self._cycle_count = 0

    def _share_url(self, target: dict) -> str:
        """Canonical /reviews/<niche>/ URL for a target, falling back to its raw link.

        Dated flat files (''.../reviews/gaming-mice/best-gaming-mice-...-2026-08-17.html'')
        are stale copies of the niche hub. The hub page — /reviews/gaming-mice/ — is the
        always-current mirror, so that is what gets shared and recorded for dedupe.
        """
        try:
            from .product_assets import slug_from_url
            slug = slug_from_url(str(target.get("url") or "")) or str(target.get("niche") or "")
        except Exception:
            slug = str(target.get("niche") or "")
        slug = (slug or "").strip().strip("/")
        if not slug:
            return str(target.get("url") or "")
        site = os.environ.get("SITE_URL", "https://abvorn.com").rstrip("/")
        return f"{site}/reviews/{slug}/"

    def _source_url(self, target: dict) -> str:
        """Dedupe key for a feed entry: its own article URL.

        Distinct from _share_url, which points social at the canonical niche
        hub. Dedupe must key on the article so a niche with many reviews yields
        many distinct posts rather than collapsing into one. The URL is
        date-normalized because the feed republishes the same article under a
        new dated filename, and those copies must count as one post.
        """
        return normalize_source_url(str(target.get("url") or "").strip())

    def _prefer_new_niche(self, candidates: list[dict]) -> dict:
        """Prefer a candidate whose niche differs from the one posted last.

        Purely a variety preference: if every remaining candidate belongs to the
        niche just posted, it returns that anyway. Without it the engine walks the
        feed in order and posts a niche twice in a row while a dozen other
        unposted niches are available.
        """
        if len(candidates) < 2:
            return candidates[0]
        last_niche = None
        try:
            times = self.learner.niche_post_times()
            if times:
                last_niche = max(times, key=lambda n: times[n])
        except Exception as e:
            logger.warning(f"last posted niche lookup failed (non-fatal): {e}")
        if last_niche is None:
            return candidates[0]
        fresh = [e for e in candidates if e.get("niche") != last_niche]
        return fresh[0] if fresh else candidates[0]

    def _rotate_target(self, entries: list[dict]) -> dict:
        """Pick the least-recently-posted niche once every article is spent.

        Without this the cycle fell back to entries[0] and re-posted the same
        top-scoring niche forever. Ties fall to the higher virality score.
        """
        times: dict[str, int] = {}
        try:
            times = self.learner.niche_post_times()
        except Exception as e:
            logger.warning(f"niche_post_times lookup failed (non-fatal): {e}")
        if not times:
            return entries[0]
        never_posted = [e for e in entries if e.get("niche") not in times]
        if never_posted:
            return never_posted[0]
        return min(
            entries,
            key=lambda e: (times.get(e.get("niche"), 0), -float(e.get("virality_score") or 0)),
        )

    def _select_target(self, entries: list[dict], posted: set[str],
                       niche: str | None = None) -> dict:
        """Choose this cycle's feed entry.

        Order: an explicit niche, else the first unposted article (preferring a
        niche other than the one posted last), else rotation across all entries
        when the feed is spent.
        """
        if niche:
            target = next(
                (e for e in entries if e["niche"] == niche and self._source_url(e) not in posted),
                None,
            )
            if target is None:
                target = next((e for e in entries if e["niche"] == niche), entries[0])
            return target
        unposted = [e for e in entries if self._source_url(e) not in posted]
        if unposted:
            return self._prefer_new_niche(unposted)
        return self._rotate_target(entries)

    def run_cycle(self, niche: str | None = None,
                  platforms: list[str] | None = None) -> dict:
        """Run one domination cycle: parse → generate → fetch → filter → publish.

        Args:
            niche: Target niche. If None, picks top-scored post.
            platforms: Target platforms. If None, all registered.

        Returns:
            Dict with cycle results.
        """
        self._cycle_count += 1
        cycle_id = f"domination_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._cycle_count}"
        logger.info(f"[{cycle_id}] Starting domination cycle")

        steps = {}

        # 1. Content Intelligence
        try:
            entries = self.content_intel.parse()
            if not entries:
                logger.warning("No RSS entries found")
                return {"cycle_id": cycle_id, "status": "no_content", "steps": steps}

            posted = set()
            try:
                posted = self.learner.posted_urls()
            except Exception as e:
                logger.warning(f"[{cycle_id}] posted_urls lookup failed (non-fatal): {e}")

            target = self._select_target(entries, posted, niche)

            # Work on a copy: step 2 rewrites target["url"] to the shared hub, and
            # mutating the caller's entry would destroy the article URL that dedupe
            # keys on, collapsing every later cycle back to the hub.
            target = dict(target)
            steps["intel"] = {
                "status": "ok",
                "title": target["title"],
                "niche": target["niche"],
                "virality_score": target["virality_score"],
                "sentiment": target["sentiment"],
            }
            # Capture the article URL before step 2 overwrites target["url"] with
            # the shared hub, otherwise the dedupe key collapses back to the hub.
            source_url = self._source_url(target)
            logger.info(f"[{cycle_id}] Intel: {target['title'][:60]}... ({target['virality_score']})")
        except Exception as e:
            logger.error(f"[{cycle_id}] Content intel failed: {e}")
            return {"cycle_id": cycle_id, "status": "intel_failed", "error": str(e)}

        # 2. Viral Script Generation
        products: list[dict] = []
        slide_url = self._share_url(target)
        # Share + record the canonical hub, not the stale dated flat file.
        target["url"] = slide_url
        try:
            from .product_assets import load_products_for_niche, slug_from_url
            _slug = slug_from_url(slide_url) or target.get("niche", "")
            products = load_products_for_niche(_slug)
            steps["products"] = {"status": "ok", "count": len(products), "slug": _slug}
            logger.info(f"[{cycle_id}] Products resolved for {_slug}: {len(products)}")
        except Exception as e:
            logger.warning(f"[{cycle_id}] Product resolution failed (non-fatal): {e}")
            steps["products"] = {"status": "failed", "error": str(e)}

        # Derive the platform set: with the gate ON the whitelist is the single
        # source of truth so every cycle targets the same channels consistently.
        effective_platforms = platforms
        if effective_platforms is None:
            try:
                from ..core.social_gate import require_social_publishing
                if require_social_publishing():
                    from ..deploy.social import _allowed_platforms
                    allowed = _allowed_platforms()
                    if allowed is not None:
                        from .viral_script_generator import PLATFORM_SPECS
                        effective_platforms = sorted(allowed & set(PLATFORM_SPECS))
            except Exception as e:
                logger.warning(f"[{cycle_id}] platform scoping failed (non-fatal): {e}")

        try:
            persona = self._resolve_persona(target.get("niche", ""))
            steps["persona"] = {"status": "ok" if persona else "none",
                                "name": persona.get("name", "") if persona else ""}
            if persona:
                logger.info(f"[{cycle_id}] Persona: {persona.get('name', '')} ({target.get('niche', '')})")
            scripts = self.script_gen.generate(
                target, platforms=effective_platforms, products=products, persona=persona,
                learner=self.learner,
            )
            steps["scripts"] = {
                "status": "ok",
                "platforms": list(scripts.keys()),
            }
            logger.info(f"[{cycle_id}] Scripts generated for {list(scripts.keys())}")
        except Exception as e:
            logger.error(f"[{cycle_id}] Script gen failed: {e}")
            steps["scripts"] = {"status": "failed", "error": str(e)}
            return {"cycle_id": cycle_id, "status": "script_failed", "steps": steps}

        # 3. Asset fetch — real product photos for every image-capable platform
        # when they exist, Pexels stock as the fallback for when no products resolve.
        media_by_platform: dict[str, list[str]] = {}
        media_paths: list[str] = []
        image_platforms = [p for p in scripts if p in {"instagram", "telegram", "linkedin", "x", "pinterest", "facebook"}]
        needs_media = bool(image_platforms)
        try:
            if products and needs_media:
                from .instagram_cards import compose_platform_media
                for p in image_platforms:
                    paths = compose_platform_media(
                        products,
                        niche=_slug,
                        title=target["title"],
                        url=slide_url,
                        platform=p,
                    )
                    media_by_platform[p] = paths
                media_paths = media_by_platform.get("instagram", [])
                steps["assets"] = {
                    "status": "ok",
                    "source": "review_product_photos",
                    "platforms": {p: len(v) for p, v in media_by_platform.items()},
                }
                logger.info(f"[{cycle_id}] Product media composed: {media_by_platform.keys()}")
            elif needs_media:
                images = self.pexels.asset_for_niche(target["niche"], count=2)
                if images:
                    for img in images[:2]:
                        if img.get("src"):
                            path = self.pexels.download_image(
                                img["src"], niche=target["niche"]
                            )
                            if path:
                                media_paths.append(path)
                                media_by_platform.setdefault("instagram", []).append(path)
                    steps["assets"] = {
                        "status": "ok",
                        "source": "pexels_stock",
                        "images_fetched": len(media_paths),
                    }
                else:
                    steps["assets"] = {"status": "no_images"}
                logger.info(f"[{cycle_id}] Pexels: {len(media_paths)} assets")
            else:
                steps["assets"] = {"status": "skipped", "reason": "no_media_platform"}
        except Exception as e:
            logger.warning(f"[{cycle_id}] Asset fetch failed (non-fatal): {e}")
            steps["assets"] = {"status": "failed", "error": str(e)}

        # 4. Cinematic Filter — brand overlay only on Pexels stock (product cards are final)
        asset_source = steps.get("assets", {}).get("source", "")
        if asset_source == "pexels_stock" and media_paths:
            try:
                for i, path in enumerate(media_paths):
                    branded = self.cinematic.apply_brand_overlay(
                        path,
                        text=target["title"][:80],
                        niche=target["niche"],
                    )
                    if branded:
                        media_paths[i] = branded
                steps["cinematic"] = {"status": "ok", "assets_processed": len(media_paths)}
                logger.info(f"[{cycle_id}] Cinematic: {len(media_paths)} processed")
            except Exception as e:
                logger.warning(f"[{cycle_id}] Cinematic filter failed (non-fatal): {e}")
                steps["cinematic"] = {"status": "failed", "error": str(e)}
        else:
            steps["cinematic"] = {"status": "skipped", "reason": asset_source or "no_media"}

        # 5. Audio System (voiceover script generation)
        try:
            for platform_key, script_data in scripts.items():
                text = self._script_to_voice_text(script_data, target)
                if text:
                    self.audio.generate_voiceover_script(
                        text, niche=target["niche"], platform=platform_key
                    )
            steps["audio"] = {"status": "ok"}
            logger.info(f"[{cycle_id}] Audio scripts generated")
        except Exception as e:
            logger.warning(f"[{cycle_id}] Audio gen failed (non-fatal): {e}")
            steps["audio"] = {"status": "failed", "error": str(e)}

        publish_results = []
        posted = []
        try:
            publish_targets = {}
            for platform_key in scripts:
                script_obj = scripts[platform_key]["script"]
                publish_targets[platform_key] = script_obj

            publish_results = self.publisher.publish_all(
                publish_targets, target["niche"], media_by_platform=media_by_platform
            )
            posted = [r for r in publish_results if r.get("status") == "posted"]
            exported = [r for r in publish_results if r.get("status") == "exported"]
            steps["publish"] = {
                "status": "ok",
                "posted": len(posted),
                "exported": len(exported),
                "results": publish_results,
            }
            logger.info(f"[{cycle_id}] Published: {len(posted)} posted, {len(exported)} exported")
        except Exception as e:
            logger.error(f"[{cycle_id}] Publish failed: {e}")
            steps["publish"] = {"status": "failed", "error": str(e)}

        try:
            recorded = []
            for result in posted:
                platform_key = str(result.get("platform") or "")
                script_data = scripts.get(platform_key)
                if not script_data:
                    continue
                hook = script_data.get("hook", "")
                if hook:
                    self.learner.record_hook_test(
                        hook, target["niche"], platform_key
                    )
                self.learner.record_post_performance(
                    url=target.get("url", ""),
                    niche=target["niche"],
                    platform=platform_key,
                    hook=hook,
                    sentiment=target.get("sentiment", "neutral"),
                    virality_score=target.get("virality_score", 0),
                    source_url=source_url,
                )
                self.learner.record_posting_time(
                    target["niche"], platform_key, target.get("virality_score", 0)
                )
                recorded.append(platform_key)
            steps["learning"] = {
                "status": "ok" if recorded else "skipped",
                "recorded": len(recorded),
            }
            if recorded:
                logger.info(f"[{cycle_id}] Learning data recorded for {len(recorded)} posts")
        except Exception as e:
            logger.warning(f"[{cycle_id}] Learning record failed (non-fatal): {e}")
            steps["learning"] = {"status": "failed", "error": str(e)}

        result = {
            "cycle_id": cycle_id,
            "status": "complete",
            "title": target["title"],
            "niche": target["niche"],
            "steps": steps,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"[{cycle_id}] Domination cycle complete")
        return result

    def run_for_all_niches(self, platforms: list[str] | None = None) -> list[dict]:
        """Run domination cycle for every niche in the RSS feed."""
        entries = self.content_intel.parse()
        niches = list(dict.fromkeys(e["niche"] for e in entries if e["niche"] != "general"))
        results = []
        for niche in niches[:3]:
            r = self.run_cycle(niche=niche, platforms=platforms)
            results.append(r)
        return results

    def _resolve_persona(self, niche: str) -> dict | None:
        """Pick the persona behind this cycle's copy.

        Preference order: live registered persona for the niche (with
        performance history) → engine template persona → None (generic copy).
        """
        try:
            lookups: list[dict | None] = []
            if self.persona_registry is not None:
                for key in (niche, niche.replace("-", " ").replace("_", " ")):
                    if key:
                        try:
                            lookups.append(self.persona_registry.select_best_persona(key))
                        except Exception as e:
                            logger.warning(f"Persona registry lookup failed: {e}")
            if self.persona_engine is not None:
                try:
                    discovered = self.persona_engine.discover_personas(niche) or []
                    lookups.extend(c for c in discovered if c)
                except Exception as e:
                    logger.warning(f"Persona engine discovery failed: {e}")
            for candidate in lookups:
                if candidate and candidate.get("psychology"):
                    return candidate
        except Exception as e:
            logger.warning(f"Persona resolution failed (non-fatal): {e}")
        return None

    def _script_to_voice_text(self, script_data: dict, target: dict) -> str:
        script = script_data.get("script", {})
        if isinstance(script, dict):
            return script.get("hook", "") + ". " + script.get("body", "")
        if isinstance(script, list):
            return ". ".join(str(s) for s in script[:3])
        return target.get("summary", "")[:300]

    def get_learning_report(self) -> str:
        return self.learner.generate_report()

    def get_stats(self) -> dict:
        return {
            "cycles_run": self._cycle_count,
            "can_post_direct": self.publisher.can_post_direct(),
            "audio_assets": self.audio.count_assets(),
            "budget": self.budget.summary(),
        }

    def get_budget_report(self) -> str:
        return self.budget.report()
