"""LongCat text-to-image/video adapter for Abvorn."""

import logging
from io import BytesIO

logger = logging.getLogger("abvorn.images")


class LongCatAdapter:
    """Adapter for LongCat text-to-video model. Handles GPU setup, inference, frame extraction."""

    def __init__(self, model_path: str = None, device: str = "cuda"):
        self.model_path = model_path
        self.device = device
        self.pipe = None
        self._loaded = False

    @property
    def available(self) -> bool:
        return self._loaded

    def load(self):
        if self._loaded:
            return True
        if not self.model_path:
            logger.warning("LongCat model path not set")
            return False
        try:
            import torch
            from diffusers import DiffusionPipeline
            self.pipe = DiffusionPipeline.from_pretrained(
                self.model_path, torch_dtype=torch.float16
            )
            self.pipe.to(self.device)
            self._loaded = True
            logger.info(f"LongCat loaded from {self.model_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load LongCat: {e}")
            return False

    def generate_image(self, prompt: str, width: int = 1200,
                       height: int = 630, num_steps: int = 30) -> bytes:
        """Generate a single image from a text prompt using LongCat."""
        if not self.load():
            return b""
        try:
            result = self.pipe(
                prompt, num_inference_steps=num_steps,
                width=width, height=height
            )
            image = result.images[0]
            buf = BytesIO()
            image.save(buf, format="PNG")
            buf.seek(0)
            logger.info(f"LongCat image: {width}x{height}")
            return buf.getvalue()
        except Exception as e:
            logger.error(f"LongCat image generation failed: {e}")
            return b""

    def generate_video(self, prompt: str, num_frames: int = 16,
                       width: int = 1080, height: int = 1920) -> bytes:
        """Generate a short video from a text prompt (future use)."""
        logger.info("LongCat video generation not yet wired")
        return b""