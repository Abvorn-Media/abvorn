"""Cinematic Filter — applies Abvorn brand styling to images using Pillow.
Creates consistent visual identity across all social assets."""

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter as PILFilter

logger = logging.getLogger("abvorn.domination.cinematic")

BRAND_OVERLAY_COLOR = (26, 26, 26)  # #1a1a1a
ACCENT_COLOR = (0, 102, 204)  # #0066cc
WHITE = (255, 255, 255)
FONT_PATH = None  # Will use default if system fonts unavailable


class CinematicFilter:
    """Applies branded cinematic overlays to images for social posts."""

    def __init__(self, font_path: str | None = None):
        self.font_path = font_path or FONT_PATH
        self._fonts_loaded = False
        self._load_fonts()

    def _load_fonts(self):
        try:
            if self.font_path and Path(self.font_path).exists():
                self.font_large = ImageFont.truetype(self.font_path, 48)
                self.font_medium = ImageFont.truetype(self.font_path, 32)
                self.font_small = ImageFont.truetype(self.font_path, 20)
            else:
                self.font_large = ImageFont.load_default()
                self.font_medium = ImageFont.load_default()
                self.font_small = ImageFont.load_default()
            self._fonts_loaded = True
        except Exception:
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            self._fonts_loaded = True

    def apply_brand_overlay(self, image_path: str, output_path: str | None = None,
                            text: str = "", niche: str = "") -> str | None:
        """Apply gradient overlay + brand text to an image."""
        try:
            img = Image.open(image_path).convert("RGB")
            draw = ImageDraw.Draw(img, "RGBA")

            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)

            for y in range(img.height):
                alpha = int(80 * (1 - y / img.height))
                overlay_draw.line([(0, y), (img.width, y)], fill=(0, 0, 0, alpha))

            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(img)

            if text:
                lines = self._wrap_text(text, self.font_large, img.width - 80)
                y_pos = img.height - len(lines) * 60 - 60
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=self.font_large)
                    tx = (img.width - (bbox[2] - bbox[0])) // 2
                    draw.text((tx + 2, y_pos + 2), line, fill=(0, 0, 0, 180), font=self.font_large)
                    draw.text((tx, y_pos), line, fill=WHITE, font=self.font_large)
                    y_pos += 55

            if niche:
                bbox = draw.textbbox((0, 0), niche.replace("-", " ").title(), font=self.font_small)
                draw.text(
                    (20, img.height - 40),
                    niche.replace("-", " ").title(),
                    fill=ACCENT_COLOR,
                    font=self.font_small,
                )

            output = output_path or image_path
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            img.save(output, quality=92)
            logger.info(f"Cinematic filter applied: {output}")
            return output

        except Exception as e:
            logger.warning(f"Cinematic filter failed: {e}")
            return None

    def create_social_card(self, niche: str, title: str, output_path: str,
                           width: int = 1080, height: int = 1080) -> str | None:
        """Create a branded social card from scratch."""
        try:
            img = Image.new("RGB", (width, height), BRAND_OVERLAY_COLOR)
            draw = ImageDraw.Draw(img)

            accent_bar = Image.new("RGB", (width, 8), ACCENT_COLOR)
            img.paste(accent_bar, (0, height // 3))

            niche_text = niche.replace("-", " ").title()
            bbox = draw.textbbox((0, 0), niche_text, font=self.font_small)
            tx = (width - (bbox[2] - bbox[0])) // 2
            draw.text((tx, height // 3 + 30), niche_text, fill=ACCENT_COLOR, font=self.font_small)

            lines = self._wrap_text(title, self.font_large, width - 80)
            y_start = height // 3 + 80
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=self.font_large)
                tx = (width - (bbox[2] - bbox[0])) // 2
                draw.text((tx, y_start), line, fill=WHITE, font=self.font_large)
                y_start += 55

            bbox = draw.textbbox((0, 0), "abvorn.com", font=self.font_small)
            draw.text(
                (width - (bbox[2] - bbox[0]) - 20, height - 40),
                "abvorn.com",
                fill=(128, 128, 128),
                font=self.font_small,
            )

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, quality=95)
            logger.info(f"Social card created: {output_path}")
            return output_path

        except Exception as e:
            logger.warning(f"Social card creation failed: {e}")
            return None

    def resize_for_platform(self, image_path: str, platform: str,
                            output_path: str | None = None) -> str | None:
        dims = {
            "x": (1200, 675),
            "instagram": (1080, 1080),
            "instagram_story": (1080, 1920),
            "tiktok": (1080, 1920),
            "linkedin": (1200, 627),
            "pinterest": (1000, 1500),
            "facebook": (1200, 630),
        }
        size = dims.get(platform, (1080, 1080))
        try:
            img = Image.open(image_path)
            img.thumbnail(size, Image.LANCZOS)
            canvas = Image.new("RGB", size, BRAND_OVERLAY_COLOR)
            x = (size[0] - img.width) // 2
            y = (size[1] - img.height) // 2
            canvas.paste(img, (x, y))
            output = output_path or image_path
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            canvas.save(output, quality=92)
            return output
        except Exception as e:
            logger.warning(f"Platform resize failed: {e}")
            return None

    def _wrap_text(self, text: str, font, max_width: int) -> list[str]:
        lines = []
        for word in text.split():
            if not lines:
                lines.append(word)
                continue
            test_line = lines[-1] + " " + word
            from PIL import ImageDraw
            temp_img = Image.new("RGB", (1, 1))
            temp_draw = ImageDraw.Draw(temp_img)
            bbox = temp_draw.textbbox((0, 0), test_line, font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                lines[-1] = test_line
            else:
                lines.append(word)
        return lines or [text[:80]]
