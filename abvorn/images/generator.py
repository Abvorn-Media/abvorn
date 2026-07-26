"""Image generation for Abvorn — prompt-driven, pluggable backends."""
import logging
from io import BytesIO

logger = logging.getLogger("abvorn.images")

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from .prompts import PromptWriter


class ImageGenerator:
    """Generates one base image per post. Prompt-driven with pluggable backends."""

    def __init__(self, backend: str = "composite", longcat_path: str = None,
                 router=None, prompt_writer: PromptWriter = None):
        self.backend = backend
        self.longcat_path = longcat_path
        self.prompt_writer = prompt_writer or PromptWriter(router=router)

    def generate(self, product_name: str, niche: str, headline: str,
                 content_type: str = "buying_guide", features: list = None,
                 output_size: tuple = (1200, 630)) -> bytes:
        prompt = self.prompt_writer.write_prompt(
            product_name, niche, headline, content_type, features
        )
        return self._generate_from_prompt(prompt, product_name, niche,
                                           content_type, output_size)

    def generate_from_prompt(self, prompt: str, product_name: str = "",
                              niche: str = "", output_size: tuple = (1200, 630)) -> bytes:
        return self._generate_from_prompt(prompt, product_name, niche,
                                           "buying_guide", output_size)

    def _generate_from_prompt(self, prompt: str, product_name: str,
                               niche: str, content_type: str,
                               output_size: tuple) -> bytes:
        if self.backend == "longcat" and self.longcat_path:
            return self._generate_longcat(prompt, output_size)
        return self._generate_composite(prompt, product_name, niche, output_size)

    def _generate_longcat(self, prompt: str, output_size: tuple) -> bytes:
        """Generate via LongCat. Requires GPU + model weights at longcat_path."""
        if not self.longcat_path:
            logger.warning("LongCat path not set — falling back to composite")
            return b""

        try:
            import torch
            from diffusers import DiffusionPipeline
            pipe = DiffusionPipeline.from_pretrained(
                self.longcat_path, torch_dtype=torch.float16
            )
            pipe.to("cuda")
            w, h = output_size
            image = pipe(
                prompt, num_inference_steps=30, width=w, height=h
            ).images[0]
            buf = BytesIO()
            image.save(buf, format="PNG")
            buf.seek(0)
            logger.info(f"LongCat generated {output_size[0]}x{output_size[1]} image")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"LongCat generation failed: {e}")
            return b""

    def _generate_composite(self, prompt: str, product_name: str,
                             niche: str, output_size: tuple) -> bytes:
        """Generate a composite image with gradient background + text overlay."""
        if not HAS_PIL:
            return b""

        w, h = output_size
        img = Image.new("RGB", (w, h), (26, 26, 26))
        draw = ImageDraw.Draw(img)

        for y in range(h):
            ratio = y / h
            r = int(26 + (40 - 26) * ratio)
            g = int(26 + (40 - 26) * ratio)
            b = int(40 + (60 - 40) * ratio)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

        niche_label = niche.replace("_", " ").title()
        draw.rectangle([20, 20, 20 + len(niche_label) * 9, 44], fill=(60, 60, 60))
        draw.text((24, 24), niche_label, fill=(180, 180, 180))

        try:
            font = ImageFont.truetype("arial.ttf", 42)
            font_small = ImageFont.truetype("arial.ttf", 22)
        except (IOError, OSError):
            font = ImageFont.load_default()
            font_small = ImageFont.load_default()

        lines = self._wrap_text(product_name or "Product", font, w - 80)
        y_start = h // 2 - len(lines) * 25
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            draw.text(((w - tw) // 2, y_start), line, fill=(255, 255, 255), font=font)
            y_start += 50

        bbox = draw.textbbox((0, 0), "Abvorn", font=font_small)
        tw = bbox[2] - bbox[0]
        draw.text((w - tw - 20, h - 35), "Abvorn", fill=(100, 120, 180), font=font_small)

        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.getvalue()

    def _wrap_text(self, text: str, font, max_width: int) -> list:
        lines = []
        words = text.split()
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            if HAS_PIL:
                bbox = font.getbbox(test)
                tw = bbox[2] - bbox[0] if bbox else 0
            else:
                tw = len(test) * 10
            if tw <= max_width:
                current = test
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [text]


def generate_post_image(product_name: str, niche: str, headline: str,
                         content_type: str = "buying_guide",
                         features: list = None,
                         backend: str = "composite") -> bytes:
    gen = ImageGenerator(backend=backend)
    return gen.generate(product_name, niche, headline, content_type, features, (1200, 630))