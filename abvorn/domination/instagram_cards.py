"""Instagram Cards — composes clean 1080x1350 (4:5) product cards from the
exact photos the review page uses, instead of letterboxed stock imagery.

Design language mirrors the website: off-white background, accent pill, real
product photo on a white card, product name + price in DejaVu Sans.
"""

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("abvorn.domination.igcards")

CANVAS = (1080, 1350)
BG = (247, 246, 242)        # off-white, site-like
WHITE = (255, 255, 255)
INK = (26, 26, 26)          # near-black text
MUTED = (120, 120, 120)
ACCENT = (0, 102, 204)      # #0066cc, site accent
CARD_BG = (255, 255, 255)
SHADOW = (210, 208, 202)


def _font(bold: bool = False, size: int = 40):
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'Bold' if bold else ''}.ttf",
        f"C:/Windows/Fonts/arial{'bd' if bold else ''}.ttf",
    ]
    for path in candidates:
        try:
            if Path(path).exists():
                return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_centered(draw: ImageDraw.ImageDraw, cx: int, y: int, text: str,
                   font: ImageFont.FreeTypeFont, fill=INK) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (bbox[2] - bbox[0]) / 2, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def _wrap(draw, text: str, font, max_width: int, max_lines: int = 2) -> list[str]:
    words = text.split()
    lines: list[str] = []
    for word in words:
        if not lines:
            lines.append(word)
            continue
        trial = lines[-1] + " " + word
        bbox = draw.textbbox((0, 0), trial, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            lines[-1] = trial
        else:
            if len(lines) >= max_lines:
                break
            lines.append(word)
    return lines or [text[:60]]


def _load_cover(path: str, box: int) -> Image.Image:
    """Fit the product photo into a box, cover-crop to a square, white-padded."""
    img = Image.open(path).convert("RGB")
    target = (box, box)
    img.thumbnail(target, Image.LANCZOS)
    canvas = Image.new("RGB", target, WHITE)
    x = (target[0] - img.width) // 2
    y = (target[1] - img.height) // 2
    canvas.paste(img, (x, y))
    return canvas


def compose_product_card(product: dict, role: str, output_path: str | Path) -> str | None:
    """Compose one 1080x1350 slide: role pill + real product photo + name + price."""
    try:
        canvas = Image.new("RGB", CANVAS, BG)
        draw = ImageDraw.Draw(canvas)

        # thin accent rule across the top
        draw.rectangle([0, 0, CANVAS[0], 14], fill=ACCENT)

        # role pill
        pill_font = _font(bold=True, size=30)
        pill_text = role.upper()
        pad = 34
        pb = draw.textbbox((0, 0), pill_text, font=pill_font)
        pill_w = (pb[2] - pb[0]) + pad * 2
        pill_h = (pb[3] - pb[1]) + 18
        pill_x = (CANVAS[0] - pill_w) // 2
        pill_y = 86
        draw.rounded_rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
                                radius=pill_h // 2, fill=ACCENT)
        _text_centered(draw, CANVAS[0] // 2, pill_y + 9, pill_text, pill_font, fill=WHITE)

        # product photo on a white card with a soft shadow
        box = 760
        card_w, card_h = box + 60, box + 60
        cx = (CANVAS[0] - card_w) // 2
        cy = 250
        draw.rounded_rectangle([cx + 6, cy + 12, cx + card_w + 6, cy + card_h + 12],
                               radius=28, fill=SHADOW)
        draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=28, fill=CARD_BG)

        photo = _load_cover(_download_image(product), box)
        draw.rounded_rectangle([cx + 32, cy + 32, cx + card_w - 32, cy + card_h - 32],
                               radius=18)
        canvas.paste(photo, (cx + 32, cy + 32))

        # name + price
        name = product.get("name", "") or "—"
        name_font = _font(bold=True, size=44)
        body = _font(size=36)
        lines = _wrap(draw, name, name_font, CANVAS[0] - 140)
        y = cy + card_h + 58
        for i, line in enumerate(lines):
            _text_centered(draw, CANVAS[0] // 2, y, line, name_font)
            y += 54
        price = product.get("price", "") or "Check price"
        price_y = y + 10
        _text_centered(draw, CANVAS[0] // 2, price_y, price, body, fill=ACCENT)

        # micro-branding
        _text_centered(draw, CANVAS[0] // 2, CANVAS[1] - 64,
                       "abvorn.com  ·  real research, not spec sheets", body, fill=MUTED)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out, quality=93)
        return str(out)
    except Exception as e:
        logger.warning(f"ig card compose failed: {e}")
        return None


def compose_cta_card(niche: str, title: str, url: str,
                     output_path: str | Path) -> str | None:
    """Final slide: point at the full guide."""
    try:
        canvas = Image.new("RGB", CANVAS, (20, 20, 20))
        draw = ImageDraw.Draw(canvas)

        def center_text(text: str, y: int, font, fill=WHITE):
            _text_centered(draw, CANVAS[0] // 2, y, text, font, fill=fill)

        niche_label = (niche or "buying guide").replace("-", " ").title()
        small = _font(bold=True, size=28)
        big = _font(bold=True, size=54)
        body = _font(size=38)
        center_text(niche_label.upper(), 250, small, fill=ACCENT)
        center_text("Full buying guide", 350, big)
        center_text("with prices, specs and a pick for every budget.", 460, body, fill=(200, 200, 200))
        center_text("abvorn.com/" + (niche or "guides"), 760, body, fill=WHITE)
        center_text("real research, not spec sheets", 900, body, fill=MUTED)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out, quality=93)
        return str(out)
    except Exception as e:
        logger.warning(f"ig cta card compose failed: {e}")
        return None


def _download_image(product: dict) -> str:
    """Persist the product photo locally (cache-first) ready for composition."""
    url = product.get("image", "")
    if not url:
        raise ValueError("no product image url")
    from .product_assets import download_product_image
    path = download_product_image(url, product.get("_slug", "general"),
                                  product.get("index", 0))
    if not path:
        raise ValueError(f"image download failed for {url}")
    return path


def compose_carousel(products: list[dict], niche: str, title: str, url: str,
                     cache_dir: str | Path | None = None,
                     cta: bool = True) -> list[str]:
    """Build the full 1080x1350 carousel deck (product slides + CTA)."""
    root = Path(cache_dir) if cache_dir else Path.home() / ".abvorn" / "exports" / "instagram"
    root.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for product in products:
        product = dict(product)
        product["_slug"] = niche
        out = compose_product_card(product, product.get("role", "Overall Winner"),
                                   root / f"card_{product.get('index', len(paths))}.jpg")
        if out:
            paths.append(out)
    if cta and products:
        cta_path = compose_cta_card(niche, title, url, root / "cta.jpg")
        if cta_path:
            paths.append(cta_path)
    return paths