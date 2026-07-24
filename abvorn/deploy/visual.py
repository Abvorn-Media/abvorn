"""Bridge between Abvorn content pipeline and Open Design for visual generation."""

import json, logging, subprocess, os
from pathlib import Path

logger = logging.getLogger("abvorn.visual")

def generate_featured_image(post_title: str, niche: str, output_dir: Path) -> str:
    """Use Open Design to generate a featured image for a blog post."""
    output_file = output_dir / "featured.html"
    try:
        subprocess.run([
            "od", "design", "featured-image",
            "--title", post_title,
            "--niche", niche,
            "--output", str(output_file),
        ], check=True, capture_output=True, timeout=60)
        logger.info(f"Featured image generated: {output_file}")
        return str(output_file)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning(f"Open Design not available for featured image: {e}")
        return ""

def generate_social_card(post_title: str, niche: str, output_dir: Path, platform: str = "x") -> str:
    """Generate a social media card for the post."""
    output_file = output_dir / f"social-{platform}.html"
    try:
        subprocess.run([
            "od", "design", "social-card",
            "--title", post_title,
            "--niche", niche,
            "--platform", platform,
            "--output", str(output_file),
        ], check=True, capture_output=True, timeout=60)
        logger.info(f"Social card generated for {platform}: {output_file}")
        return str(output_file)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning(f"Open Design not available for social card: {e}")
        return ""