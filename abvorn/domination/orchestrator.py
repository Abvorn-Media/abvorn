"""Domination Orchestrator — The Brain of the social domination engine.

Orchestrates the full pipeline:
1. Content Intelligence → parse RSS, score virality
2. Viral Script Generator → platform-native scripts with hooks
3. Pexels Asset Fetcher → images/videos for each post
4. Cinematic Filter → brand overlays on images
5. Audio System → voiceover scripts
6. Self-Learning Engine → record + optimize
7. Social Publisher → Composio publish or export

Designed to run as a scheduled task within the Abvorn daemon.
"""

import logging
from datetime import datetime

from .content_intelligence import ContentIntelligence
from .viral_script_generator import ViralScriptGenerator
from .pexels_asset_fetcher import PexelsAssetFetcher
from .cinematic_filter import CinematicFilter
from .audio_system import AudioSystem
from .self_learning_engine import SelfLearningEngine
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
    ):
        self.budget = budget or APIBudget()
        self.content_intel = ContentIntelligence(rss_url=rss_url, rss_path=rss_path)
        self.script_gen = ViralScriptGenerator()
        self.pexels = PexelsAssetFetcher(api_key=pexels_key, budget=self.budget)
        self.cinematic = CinematicFilter()
        self.audio = AudioSystem()
        self.learner = SelfLearningEngine(db_path=db_path)
        self.publisher = SocialPublisher(composio_key=composio_key)

        self._cycle_count = 0

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

            if niche:
                target = next((e for e in entries if e["niche"] == niche), entries[0])
            else:
                target = entries[0]

            steps["intel"] = {
                "status": "ok",
                "title": target["title"],
                "niche": target["niche"],
                "virality_score": target["virality_score"],
                "sentiment": target["sentiment"],
            }
            logger.info(f"[{cycle_id}] Intel: {target['title'][:60]}... ({target['virality_score']})")
        except Exception as e:
            logger.error(f"[{cycle_id}] Content intel failed: {e}")
            return {"cycle_id": cycle_id, "status": "intel_failed", "error": str(e)}

        # 2. Viral Script Generation
        try:
            scripts = self.script_gen.generate(target, platforms=platforms)
            steps["scripts"] = {
                "status": "ok",
                "platforms": list(scripts.keys()),
            }
            logger.info(f"[{cycle_id}] Scripts generated for {list(scripts.keys())}")
        except Exception as e:
            logger.error(f"[{cycle_id}] Script gen failed: {e}")
            steps["scripts"] = {"status": "failed", "error": str(e)}
            return {"cycle_id": cycle_id, "status": "script_failed", "steps": steps}

        # 3. Pexels Asset Fetch
        media_paths = []
        try:
            images = self.pexels.asset_for_niche(target["niche"], count=2)
            if images:
                for img in images[:2]:
                    if img.get("src"):
                        path = self.pexels.download_image(
                            img["src"], niche=target["niche"]
                        )
                        if path:
                            media_paths.append(path)
                steps["pexels"] = {
                    "status": "ok",
                    "images_fetched": len(media_paths),
                }
            else:
                steps["pexels"] = {"status": "no_images"}
            logger.info(f"[{cycle_id}] Pexels: {len(media_paths)} assets")
        except Exception as e:
            logger.warning(f"[{cycle_id}] Pexels fetch failed (non-fatal): {e}")
            steps["pexels"] = {"status": "failed", "error": str(e)}

        # 4. Cinematic Filter
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

        # 6. Self-Learning (record hooks for future optimization)
        try:
            for platform_key, script_data in scripts.items():
                hook = script_data.get("hook", "")
                if hook:
                    hook_id = self.learner.record_hook_test(
                        hook, target["niche"], platform_key
                    )
                    self.learner.record_post_performance(
                        url=target.get("url", ""),
                        niche=target["niche"],
                        platform=platform_key,
                        hook=hook,
                        sentiment=target.get("sentiment", "neutral"),
                        virality_score=target.get("virality_score", 0),
                    )
            self.learner.record_posting_time(target["niche"], "blog", target["virality_score"])
            steps["learning"] = {"status": "ok"}
            logger.info(f"[{cycle_id}] Learning data recorded")
        except Exception as e:
            logger.warning(f"[{cycle_id}] Learning record failed (non-fatal): {e}")
            steps["learning"] = {"status": "failed", "error": str(e)}

        # 7. Publish
        try:
            publish_targets = {}
            for platform_key in scripts:
                script_obj = scripts[platform_key]["script"]
                publish_targets[platform_key] = script_obj

            publish_results = self.publisher.publish_all(publish_targets, target["niche"])
            posted = [r for r in publish_results if r["status"] == "posted"]
            exported = [r for r in publish_results if r["status"] == "exported"]
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
