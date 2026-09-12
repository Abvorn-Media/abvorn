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


# Canonical per-platform frame sizes: what should be attached when real
# product photos are available. These match CinematicFilter.resize_for_platform
# so the publishing pipeline uses one source of truth for framing.
PLATFORM_DIMS = {
    "instagram": (1080, 1350),
    "telegram": (1080, 1350),
    "linkedin": (1200, 627),
    "x": (1200, 675),
    "facebook": (1200, 630),
    "pinterest": (1000, 1500),
}
LANDSCAPE_PLATFORMS = {"linkedin", "x", "facebook"}


def compose_product_card(product: dict, role: str, output_path: str | Path,
                         size: tuple[int, int] | None = None) -> str | None:
    """Compose one vertical slide — role pill + real product photo + name + price — at
    the requested size.  Defaults to the 1080x1350 (4:5) Instagram canvas; Pinterest
    supplies (1000, 1500) so the same product photo card is produced in 2:3 form."""
    W, H = size if size else CANVAS
    sx, sy = W / CANVAS[0], H / CANVAS[1]
    fs = max(0.7, min(sx, sy))
    try:
        canvas = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(canvas)

        # thin accent rule across the top
        draw.rectangle([0, 0, W, max(8, round(14 * sy))], fill=ACCENT)

        # role pill
        pill_font = _font(bold=True, size=round(30 * fs))
        pill_text = role.upper()
        pad = round(34 * fs)
        pb = draw.textbbox((0, 0), pill_text, font=pill_font)
        pill_w = (pb[2] - pb[0]) + pad * 2
        pill_h = (pb[3] - pb[1]) + round(18 * fs)
        pill_x = (W - pill_w) // 2
        pill_y = round(86 * sy)
        draw.rounded_rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
                                radius=pill_h // 2, fill=ACCENT)
        _text_centered(draw, W // 2, pill_y + round(9 * fs), pill_text, pill_font, fill=WHITE)

        # product photo on a white card with a soft shadow
        box = round(760 * sx)
        card_w, card_h = box + round(60 * fs), box + round(60 * fs)
        cx = (W - card_w) // 2
        cy = round(250 * sy)
        draw.rounded_rectangle([cx + 6, cy + 12, cx + card_w + 6, cy + card_h + 12],
                               radius=28, fill=SHADOW)
        draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=28, fill=CARD_BG)

        photo = _load_cover(_download_image(product), box)
        inset = round(32 * fs)
        draw.rounded_rectangle([cx + inset, cy + inset, cx + card_w - inset, cy + card_h - inset],
                               radius=18)
        canvas.paste(photo, (cx + inset, cy + inset))

        # name + price
        name = product.get("name", "") or "—"
        name_font = _font(bold=True, size=round(44 * fs))
        body = _font(size=round(36 * fs))
        lines = _wrap(draw, name, name_font, W - round(140 * fs))
        y = cy + card_h + round(58 * sy)
        for line in lines:
            _text_centered(draw, W // 2, y, line, name_font)
            y += round(54 * sy)
        price = product.get("price", "") or "Check price"
        _text_centered(draw, W // 2, y + round(10 * sy), price, body, fill=ACCENT)

        # micro-branding
        _text_centered(draw, W // 2, H - round(64 * sy),
                       "abvorn.com  ·  real research, not spec sheets", body, fill=MUTED)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out, quality=93)
        return str(out)
    except Exception as e:
        logger.warning(f"ig card compose failed: {e}")
        return None


def compose_landscape_card(product: dict, role: str, url: str,
                           output_path: str | Path,
                           size: tuple[int, int]) -> str | None:
    """Compose a landscape share card (LinkedIn / X / Facebook share sizes):
    product photo on the left, role + name + price + URL on the right."""
    W, H = size
    fs = W / 1200.0
    try:
        canvas = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(canvas)

        # thin accent rule across the top
        draw.rectangle([0, 0, W, max(8, round(14 * fs))], fill=ACCENT)

        # left: product photo on a white card
        box = round(min(H - 220, W * 0.42))
        card_w, card_h = box + round(60 * fs), box + round(60 * fs)
        cx = round(50 * fs)
        cy = round((H - card_h) / 2)
        draw.rounded_rectangle([cx + 6, cy + 12, cx + card_w + 6, cy + card_h + 12],
                               radius=28, fill=SHADOW)
        draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=28, fill=CARD_BG)
        photo = _load_cover(_download_image(product), box)
        inset = round(32 * fs)
        draw.rounded_rectangle([cx + inset, cy + inset, cx + card_w - inset, cy + card_h - inset],
                               radius=18)
        canvas.paste(photo, (cx + inset, cy + inset))

        # right: role pill, name, price, URL
        tx = cx + card_w + round(56 * fs)
        tw = W - tx - round(56 * fs)

        pill_font = _font(bold=True, size=round(28 * fs))
        pill_text = role.upper()
        pad = round(28 * fs)
        pb = draw.textbbox((0, 0), pill_text, font=pill_font)
        pill_w = (pb[2] - pb[0]) + pad * 2
        pill_h = (pb[3] - pb[1]) + round(16 * fs)
        draw.rounded_rectangle([tx, cy, tx + pill_w, cy + pill_h], radius=pill_h // 2, fill=ACCENT)
        draw.text((tx + pad, cy + round(8 * fs)), pill_text, font=pill_font, fill=WHITE)

        name_font = _font(bold=True, size=round(44 * fs))
        name_lines = _wrap(draw, product.get("name", "") or "—", name_font, tw, max_lines=3)
        y = cy + pill_h + round(26 * fs)
        for line in name_lines:
            draw.text((tx, y), line, font=name_font, fill=INK)
            y += round(56 * fs)

        price_font = _font(size=round(38 * fs))
        draw.text((tx, y), product.get("price", "") or "Check price",
                  font=price_font, fill=ACCENT)

        y = H - round(64 * fs)
        body = _font(size=round(24 * fs))
        draw.text((tx, y), url.strip(), font=body, fill=MUTED)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out, quality=93)
        return str(out)
    except Exception as e:
        logger.warning(f"landscape card compose failed: {e}")
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


def compose_platform_media(products: list[dict], niche: str, title: str, url: str,
                           platform: str,
                           cache_dir: str | Path | None = None) -> list[str]:
    """Build real-product-photo media for any image-capable platform.

    Instagram & Telegram get a vertical carousel deck (1080x1350 cards); the
    landscape share platforms (LinkedIn, X, Facebook) get one horizontal card
    per product at their share size; Pinterest gets 2:3 pins.  Falls back to
    [] when no products/photo resolve, leaving the caller's Pexels path intact.
    """
    if not products:
        return []
    root = Path(cache_dir) if cache_dir \
        else Path.home() / ".abvorn" / "exports" / platform
    root.mkdir(parents=True, exist_ok=True)

    if platform in ("instagram", "telegram"):
        return compose_carousel(products, niche, title, url, cache_dir=root)

    if platform == "pinterest":
        pin_dir = root / "pins"
        paths = []
        for product in products:
            product = dict(product)
            product["_slug"] = niche
            out = compose_product_card(product, product.get("role", "Overall Winner"),
                                       pin_dir / f"pin_{product.get('index', len(paths))}.jpg",
                                       size=PLATFORM_DIMS["pinterest"])
            if out:
                paths.append(out)
        return paths

    dims = PLATFORM_DIMS.get(platform)
    if platform in LANDSCAPE_PLATFORMS and dims:
        paths = []
        for product in products:
            product = dict(product)
            product["_slug"] = niche
            out = compose_landscape_card(product, product.get("role", "Overall Winner"),
                                         url,
                                         root / f"share_{product.get('index', len(paths))}.jpg",
                                         size=dims)
            if out:
                paths.append(out)
        return paths
    return []