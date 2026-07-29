"""Content pipeline — orchestrates product data into platform-optimized content assets."""

import os
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.humanizer_engine import HumanizerEngine
from src.fact_checker_guard import FactCheckerGuard, create_fact_checker
from src.quantum_content_engine import QuantumContentEngine, create_quantum_engine, Platform

logger = logging.getLogger("abvorn.content_pipeline")

_humanizer = HumanizerEngine()

ASSETS_DIR = Path("assets")
OUTPUT_DIR = Path("output")
DATA_PROCESSED = Path("data/processed")

PLATFORMS = ["tiktok", "instagram_reel", "youtube_short", "x", "linkedin"]


class ContentPipeline:
    """
    Orchestrates the end-to-end content creation process.
    
    Input: product_id (matches a file in data/processed/)
    Output: scripts, hero images, and publication-ready content.
    """

    def __init__(self):
        self._ensure_dirs()
        self.fact_checker = create_fact_checker()
        self.quantum_engine = create_quantum_engine()

    def _ensure_dirs(self):
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    def load_verdict(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Load a verdict from data/processed/."""
        path = DATA_PROCESSED / f"{product_id}_verdict.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        path2 = DATA_PROCESSED / f"{product_id}.json"
        if path2.exists():
            return json.loads(path2.read_text(encoding="utf-8"))
        logger.warning(f"Verdict not found for {product_id}")
        return None

    def load_raw(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Load raw product data from data/raw/."""
        path = Path("data/raw") / f"{product_id}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def generate_scripts(self, verdict: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Generate platform-optimized viral scripts from verdict data."""
        from src.script_generator import generate_viral_script
        scripts = {}
        for platform in PLATFORMS:
            try:
                script = generate_viral_script(verdict, platform)
                scripts[platform] = script
                logger.info(f"  Script ({platform}): {script['word_count']} words")
            except Exception as e:
                logger.error(f"Script generation failed for {platform}: {e}")
                scripts[platform] = {"error": str(e)}
        return scripts

    def generate_hero_image(self, product_name: str, score: float, 
                            product_id: str = "") -> str:
        """
        Generate a hero image placeholder.
        
        In production, this calls _gen_sleek_images.py or the图像生成 pipeline.
        Returns the path to the generated image.
        """
        safe_name = product_name.lower().replace(" ", "-")[:40]
        filename = f"{product_id or safe_name}_hero.png"
        output_path = ASSETS_DIR / filename

        try:
            result = subprocess.run(
                ["python", "_gen_sleek_images.py",
                 "--product", product_name,
                 "--score", str(score),
                 "--output", str(output_path)],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and output_path.exists():
                logger.info(f"  Hero image: {output_path}")
                return str(output_path)
        except Exception as e:
            logger.warning(f"Image generation failed: {e}")

        # Fallback: create a simple HTML-based image placeholder marker
        placeholder = ASSETS_DIR / f"{product_id or safe_name}_hero.txt"
        placeholder.write_text(f"Hero image for: {product_name} (score: {score})")
        logger.info(f"  Placeholder created: {placeholder}")
        return str(placeholder)

    def generate_title(self, verdict: Dict[str, Any], platform: str) -> str:
        """Generate and humanize a platform-optimized title."""
        product_name = verdict.get("product_name", "Product")
        overall = verdict.get("overall", 0)
        label = verdict.get("label", "")

        templates = {
            "tiktok": f"Is this the best {product_name}?",
            "youtube_short": f"{product_name} — {label} review ({overall}/10)",
            "instagram_reel": f"Rating the {product_name}: {label}",
            "x": f"{product_name} review: {label}",
            "linkedin": f"Deep dive: {product_name} — {label} with {overall}/10",
        }
        raw_title = templates.get(platform, templates["youtube_short"])
        return _humanizer.humanize_video_title(raw_title, platform)

    def generate_description(self, verdict: Dict[str, Any], platform: str) -> str:
        """Generate and humanize a platform-optimized description."""
        product_name = verdict.get("product_name", "Product")
        overall = verdict.get("overall", 0)
        summary = verdict.get("summary", "")

        raw_desc = f"{product_name} — rated {overall}/10. {summary}"
        return _humanizer.humanize_description(raw_desc, platform)

    def generate_thumbnail_text(self, verdict: Dict[str, Any]) -> str:
        """Generate humanized thumbnail text."""
        product_name = verdict.get("product_name", "Product")
        overall = verdict.get("overall", 0)
        label = verdict.get("label", "")
        raw_text = f"{product_name}\n{overall}/10 {label}"
        return _humanizer.humanize_thumbnail_text(raw_text)

    def generate_voiceover(self, verdict: Dict[str, Any]) -> str:
        """Generate humanized voiceover script from verdict summary."""
        summary = verdict.get("summary", "")
        product_name = verdict.get("product_name", "Product")
        raw_vo = f"Today we are reviewing the {product_name}. Here is our verdict: {summary}"
        return _humanizer.humanize_voiceover_script(raw_vo)

    def create_content(self, product_id: str) -> Dict[str, Any]:
        """
        Full content creation pipeline for one product.
        
        Steps:
        1. Load verdict + raw data
        2. Generate scripts for each platform
        3. Generate hero image
        4. Return complete content package
        """
        logger.info(f"🚀 Creating content for: {product_id}")

        verdict = self.load_verdict(product_id)
        if not verdict:
            return {"status": "error", "message": f"Verdict not found for {product_id}"}

        raw = self.load_raw(product_id) or {}
        product_name = verdict.get("product_name", product_id)
        overall = verdict.get("overall", 0)

        logger.info(f"  Product: {product_name} — Score: {overall}")

        scripts = self.generate_scripts(verdict)
        image_path = self.generate_hero_image(product_name, overall, product_id)

        titles = {}
        descriptions = {}
        thumbnail_text = ""
        voiceover = ""
        for platform in PLATFORMS:
            titles[platform] = self.generate_title(verdict, platform)
            descriptions[platform] = self.generate_description(verdict, platform)
        thumbnail_text = self.generate_thumbnail_text(verdict)
        voiceover = self.generate_voiceover(verdict)

        result = {
            "product_id": product_id,
            "product_name": product_name,
            "verdict": verdict,
            "raw_data": raw,
            "scripts": scripts,
            "titles": titles,
            "descriptions": descriptions,
            "thumbnail_text": thumbnail_text,
            "voiceover": voiceover,
            "hero_image": image_path,
            "created_at": datetime.now().isoformat(),
        }

        # Fact-check all generated content
        for platform, script_data in scripts.items():
            if isinstance(script_data, dict) and "script" in script_data:
                fc = self.fact_checker.check_content(script_data["script"], context={"platform": platform})
                if fc["overall_status"] == "critical":
                    logger.warning(f"  Fact-check CRITICAL for {platform}: {len(fc['failed_claims'])} failed claims")
                elif fc["failed_claims"]:
                    script_data["script"] = self.fact_checker.apply_corrections(
                        script_data["script"], fc["corrections"])
                    logger.info(f"  Fact-check fixes applied for {platform}: {len(fc['corrections'])}")

        # Quantum engagement simulation
        try:
            user_data = {"interest_score": 0.7}
            for platform_str in ["tiktok", "youtube_short", "instagram_reel", "x", "linkedin"]:
                platform_map = {"tiktok": Platform.TIKTOK, "youtube_short": Platform.YOUTUBE, "instagram_reel": Platform.INSTAGRAM, "x": Platform.X, "linkedin": Platform.LINKEDIN}
                plat = platform_map.get(platform_str)
                if plat:
                    simulation = self.quantum_engine.simulate_content(verdict, user_data, plat)
                    assembled = self.quantum_engine.assemble_content(simulation, verdict, plat)
                    if isinstance(scripts.get(platform_str), dict):
                        scripts[platform_str]["predicted_engagement"] = assembled["predictions"]["engagement_score"]
                        scripts[platform_str]["predicted_views"] = assembled["predictions"]["views"]
                        scripts[platform_str]["predicted_components"] = assembled["components"]
        except Exception as e:
            logger.warning(f"Quantum simulation skipped: {e}")

        self._save_pipeline_result(result)
        return result

    def create_content_for_niche(self, niche: str, product_name: str = "") -> Dict[str, Any]:
        """
        Full content pipeline for a niche: ingest data, score, create content.
        """
        from src.data_ingestion import ingest_niche, ingest_product_data

        logger.info(f"📥 Ingesting data for niche: {niche}")
        ingest_data = ingest_niche(niche, product_name)

        if product_name and ingest_data.get("product_data"):
            pid = ingest_data["product_data"].get("product_id", "")
        else:
            articles = ingest_data.get("articles", [])
            pid = f"{niche}-rss-{datetime.now().strftime('%Y%m%d')}"

        content = self.create_content(pid)
        return content

    def _save_pipeline_result(self, result: Dict[str, Any]):
        """Save pipeline output."""
        out_dir = Path("data/pipeline")
        out_dir.mkdir(parents=True, exist_ok=True)
        pid = result.get("product_id", "unknown")
        path = out_dir / f"{pid}_pipeline.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Pipeline result saved: {path}")


def run_pipeline_once():
    """Run a single pipeline cycle (used by run_cycle.py or scheduler)."""
    pipeline = ContentPipeline()
    # Process any products in data/processed that don't yet have pipeline results
    processed_dir = Path("data/processed")
    if not processed_dir.exists():
        logger.info("No processed data found — nothing to pipeline")
        return {"status": "idle", "products": 0}

    verdict_files = list(processed_dir.glob("*_verdict.json"))
    results = []
    for vf in verdict_files:
        product_id = vf.stem.replace("_verdict", "")
        try:
            result = pipeline.create_content(product_id)
            results.append(result)
        except Exception as e:
            logger.error(f"Pipeline failed for {product_id}: {e}")
            results.append({"product_id": product_id, "status": "error", "message": str(e)})

    return {"status": "complete", "products": len(results), "results": results}


if __name__ == "__main__":
    result = run_pipeline_once()
    print(json.dumps(result, indent=2, ensure_ascii=False))