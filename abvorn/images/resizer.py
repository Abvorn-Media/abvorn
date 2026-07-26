"""Image resizer — one base image → platform-optimized variants."""

import logging
from io import BytesIO

logger = logging.getLogger("abvorn.images")

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

PLATFORM_DIMENSIONS = {
    "og": (1200, 630),
    "blog": (1200, 630),
    "x": (1200, 675),
    "linkedin": (1200, 675),
    "instagram": (1080, 1080),
    "tiktok": (1080, 1920),
    "pinterest": (1000, 1500),
    "facebook": (1200, 630),
    "email": (600, 315),
}


class ImageResizer:
    """Takes a base image and outputs platform-specific sizes."""

    def resize(self, image_bytes: bytes, platform: str) -> bytes:
        target = PLATFORM_DIMENSIONS.get(platform)
        if not target:
            return image_bytes
        if not HAS_PIL:
            return image_bytes

        img = Image.open(BytesIO(image_bytes))
        resized = self._cover_fit(img, target)
        buf = BytesIO()
        resized.save(buf, format="PNG")
        buf.seek(0)
        return buf.getvalue()

    def resize_all(self, image_bytes: bytes) -> dict:
        return {
            platform: self.resize(image_bytes, platform)
            for platform in PLATFORM_DIMENSIONS
        }

    def _cover_fit(self, img: Image.Image, target: tuple) -> Image.Image:
        tw, th = target
        ow, oh = img.size
        scale = max(tw / ow, th / oh)
        new_w = int(ow * scale)
        new_h = int(oh * scale)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - tw) // 2
        top = (new_h - th) // 2
        return resized.crop((left, top, left + tw, top + th))