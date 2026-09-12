"""Instagram Cards — composes clean 1080x1350 (4:5) product cards from the
exact photos the review page uses, instead of letterboxed stock imagery.

Design language mirrors the website: off-white background, gold accent glow
dot eyebrow, real product photo on a white card, product name in tracked
Libre Franklin 800, price in JetBrains Mono, and an optional verdict strip.
"""

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger("abvorn.domination.igcards")

CANVAS = (1080, 1350)
BG = (246, 245, 242)        # #f6f5f2 off-white
WHITE = (255, 255, 255)
INK = (10, 10, 10)          # #0a0a0a
MUTED = (102, 102, 102)     # #666
ACCENT = (201, 138, 44)     # #c98a2c gold
ACCENT_DARK = (153, 96, 21) # #996015
SHADOW = (210, 207, 199)
CARD_BG = WHITE

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FONT_DIR = _REPO_ROOT / "assets" / "fonts"


def _font(role: str = "display", size: int = 40) -> ImageFont.FreeTypeFont:
    try:
        if role == "display":
            p = _FONT_DIR / "LibreFranklin-Variable.ttf"
            if p.exists():
                f = ImageFont.truetype(str(p), size)
                if hasattr(f, "set_variation_by_axes"):
                    f.set_variation_by_axes([800])
                    return f
        elif role == "mono":
            p = _FONT_DIR / "JetBrainsMono-Variable.ttf"
            if p.exists():
                f = ImageFont.truetype(str(p), size)
                if hasattr(f, "set_variation_by_axes"):
                    f.set_variation_by_axes([700])
                    return f
        else:
            p = _FONT_DIR / "LibreFranklin-Variable.ttf"
            if p.exists():
                f = ImageFont.truetype(str(p), size)
                if hasattr(f, "set_variation_by_axes"):
                    f.set_variation_by_axes([600])
                    return f
    except Exception:
        pass
    candidates = {
        "display": [
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ],
        "mono": [
            "C:/Windows/Fonts/consola.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        ],
        "body": [
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ],
    }
    for fp in candidates.get(role, []):
        try:
            if Path(fp).exists():
                return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _text_width(draw: ImageDraw.ImageDraw, text: str, font, tracking: float) -> float:
    w = 0.0
    for i, ch in enumerate(text):
        w += draw.textlength(ch, font=font)
        if i < len(text) - 1:
            w += tracking
    return w


def _draw_tracked(draw: ImageDraw.ImageDraw, x: int, y: int, text: str,
                  font, tracking: float, fill) -> None:
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking


def _draw_tracked_centered(draw: ImageDraw.ImageDraw, cx: int, y: int,
                           text: str, font, tracking: float, fill) -> None:
    total = _text_width(draw, text, font, tracking)
    x = int(cx - total / 2)
    _draw_tracked(draw, x, y, text, font, tracking, fill)


def _wrap_tracked(draw: ImageDraw.ImageDraw, text: str, font,
                  max_width: float, tracking: float,
                  max_lines: int = 2) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    current_w = 0.0
    for word in words:
        word_w = (
            sum(draw.textlength(ch, font=font) for ch in word)
            + tracking * max(0, len(word) - 1)
        )
        space_w = draw.textlength(" ", font=font) + tracking
        if not current:
            current = [word]
            current_w = word_w
        else:
            if current_w + space_w + word_w <= max_width:
                current.append(word)
                current_w += space_w + word_w
            else:
                lines.append(" ".join(current))
                if len(lines) >= max_lines:
                    break
                current = [word]
                current_w = word_w
    if current and len(lines) < max_lines:
        lines.append(" ".join(current))
    return lines or [text[:60]]


def _glow_dot(canvas: Image.Image, cx: int, cy: int, size: int, color: tuple) -> None:
    """Square accent dot with a soft luminous halo (site signature)."""
    radius = max(1, int(size * 1.6))
    overlay = Image.new("RGBA", (radius * 2, radius * 2), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((0, 0, radius * 2 - 1, radius * 2 - 1), fill=(*color, 110))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=max(1, radius // 2 + 1)))
    canvas.alpha_composite(overlay, (cx - radius, cy - radius))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle(
        (cx - size // 2, cy - size // 2, cx + size // 2 + 1, cy + size // 2 + 1),
        radius=2,
        fill=color,
    )


def _verdict_label(score) -> str:
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "SOLID"
    if s >= 7:
        return "GOOD"
    if s >= 5:
        return "SOLID"
    return "WORTH A LOOK"


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
    """Compose one vertical slide — glowing-dot eyebrow + real product photo +
    name + price — at the requested size.  Defaults to the 1080x1350 (4:5)
    Instagram canvas; Pinterest supplies (1000, 1500) for 2:3 pins.

    If ``product`` contains a ``score`` key (numeric 1-10), a verdict strip
    is rendered above the micro-branding footer.
    """
    W, H = size if size else CANVAS
    sx, sy = W / CANVAS[0], H / CANVAS[1]
    fs = max(0.7, min(sx, sy))
    try:
        canvas = Image.new("RGBA", (W, H), (*BG, 255))
        draw = ImageDraw.Draw(canvas)

        # thin accent rule across the top
        draw.rectangle([0, 0, W, max(8, round(14 * sy))], fill=ACCENT)

        # signature glow dot + role eyebrow
        dot_size = round(10 * fs)
        dot_x = round(60 * sx)
        dot_y = round(116 * sy)
        _glow_dot(canvas, dot_x, dot_y, dot_size, ACCENT)
        draw = ImageDraw.Draw(canvas)
        mono = _font("mono", round(22 * fs))
        _draw_tracked(
            draw,
            dot_x + round(18 * fs),
            dot_y - round(6 * fs),
            role.upper(),
            mono,
            round(2 * fs),
            ACCENT,
        )

        # product photo on a white card with a soft shadow
        box = round(760 * sx)
        card_w, card_h = box + round(60 * fs), box + round(60 * fs)
        cx = (W - card_w) // 2
        cy = round(220 * sy)
        draw.rounded_rectangle(
            [cx + 6, cy + 12, cx + card_w + 6, cy + card_h + 12],
            radius=28,
            fill=SHADOW,
        )
        draw.rounded_rectangle(
            [cx, cy, cx + card_w, cy + card_h], radius=28, fill=CARD_BG
        )

        photo = _load_cover(_download_image(product), box)
        inset = round(32 * fs)
        draw.rounded_rectangle(
            [cx + inset, cy + inset, cx + card_w - inset, cy + card_h - inset],
            radius=18,
        )
        canvas.paste(photo, (cx + inset, cy + inset))

        # name + price
        name = product.get("name", "") or "—"
        name_font = _font("display", round(44 * fs))
        price_font = _font("mono", round(34 * fs))
        lines = _wrap_tracked(draw, name, name_font, W - round(140 * fs), -1)
        y = cy + card_h + round(48 * sy)
        for line in lines:
            _draw_tracked_centered(draw, W // 2, y, line, name_font, -1, INK)
            y += round(54 * sy)

        price = product.get("price", "") or "Check price"
        _draw_tracked_centered(
            draw, W // 2, y + round(10 * sy), price, price_font, 0, ACCENT_DARK
        )

        # optional verdict strip
        if product.get("score") is not None:
            score_text = f"{product['score']}/10"
            label = _verdict_label(product["score"])
            score_font = _font("display", round(64 * fs))
            lbl_font = _font("mono", round(24 * fs))
            sw = _text_width(draw, score_text, score_font, -1)
            lw = _text_width(draw, label, lbl_font, 1)
            total = sw + round(16 * fs) + lw
            sx_pos = int(W // 2 - total // 2)
            _draw_tracked(draw, sx_pos, H - round(260 * sy), score_text, score_font, -1, INK)
            _draw_tracked(
                draw,
                sx_pos + int(sw) + round(16 * fs),
                H - round(228 * sy),
                label,
                lbl_font,
                1,
                MUTED,
            )

        # micro-branding
        micro_font = _font("mono", round(22 * fs))
        micro = "abvorn.com  ·  real research, not spec sheets"
        _draw_tracked_centered(
            draw, W // 2, H - round(64 * sy), micro, micro_font, 1, MUTED
        )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert("RGB").save(out, quality=93)
        return str(out)
    except Exception as e:
        logger.warning(f"ig card compose failed: {e}")
        return None


def compose_landscape_card(product: dict, role: str, url: str,
                           output_path: str | Path,
                           size: tuple[int, int]) -> str | None:
    """Compose a landscape share card (LinkedIn / X / Facebook share sizes):
    product photo on the left, glow-dot eyebrow + role + name + price + URL
    on the right."""
    W, H = size
    fs = W / 1200.0
    try:
        canvas = Image.new("RGBA", (W, H), (*BG, 255))
        draw = ImageDraw.Draw(canvas)

        # thin accent rule across the top
        draw.rectangle([0, 0, W, max(8, round(14 * fs))], fill=ACCENT)

        # left: product photo on a white card
        box = round(min(H - 220, W * 0.42))
        card_w, card_h = box + round(60 * fs), box + round(60 * fs)
        cx = round(50 * fs)
        cy = int((H - card_h) / 2)
        draw.rounded_rectangle(
            [cx + 6, cy + 12, cx + card_w + 6, cy + card_h + 12],
            radius=28,
            fill=SHADOW,
        )
        draw.rounded_rectangle(
            [cx, cy, cx + card_w, cy + card_h], radius=28, fill=CARD_BG
        )
        photo = _load_cover(_download_image(product), box)
        inset = round(32 * fs)
        draw.rounded_rectangle(
            [cx + inset, cy + inset, cx + card_w - inset, cy + card_h - inset],
            radius=18,
        )
        canvas.paste(photo, (cx + inset, cy + inset))

        # right: glow-dot eyebrow, name, price, URL
        tx = cx + card_w + round(56 * fs)
        tw = W - tx - round(56 * fs)

        dot_size = round(8 * fs)
        _glow_dot(canvas, int(tx + dot_size // 2), int(cy + round(14 * fs)), dot_size, ACCENT)
        draw = ImageDraw.Draw(canvas)
        mono = _font("mono", round(22 * fs))
        _draw_tracked(
            draw,
            int(tx + dot_size + round(12 * fs)),
            int(cy + round(4 * fs)),
            role.upper(),
            mono,
            round(2 * fs),
            ACCENT,
        )

        name_font = _font("display", round(44 * fs))
        name_lines = _wrap_tracked(
            draw, product.get("name", "") or "—", name_font, tw, -1, max_lines=3
        )
        y = cy + round(52 * fs)
        for line in name_lines:
            _draw_tracked(draw, int(tx), int(y), line, name_font, -1, INK)
            y += round(56 * fs)

        price_font = _font("mono", round(34 * fs))
        _draw_tracked(
            draw,
            int(tx),
            int(y),
            product.get("price", "") or "Check price",
            price_font,
            0,
            ACCENT_DARK,
        )

        body = _font("mono", round(22 * fs))
        _draw_tracked(draw, int(tx), int(H - round(64 * fs)), url.strip(), body, 1, MUTED)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert("RGB").save(out, quality=93)
        return str(out)
    except Exception as e:
        logger.warning(f"landscape card compose failed: {e}")
        return None


def compose_cta_card(niche: str, title: str, url: str,
                     output_path: str | Path) -> str | None:
    """Final slide: dark bg, glow-dot 'BUYING GUIDE' eyebrow, title,
    tagline, and URL."""
    W, H = CANVAS
    try:
        canvas = Image.new("RGBA", (W, H), (*INK, 255))
        draw = ImageDraw.Draw(canvas)

        draw.rectangle([0, 0, W, max(8, round(14))], fill=ACCENT)

        _glow_dot(canvas, 60, 116, 10, ACCENT)
        draw = ImageDraw.Draw(canvas)
        mono = _font("mono", 22)
        _draw_tracked(draw, 78, 110, "BUYING GUIDE", mono, 2, ACCENT)

        title_font = _font("display", 54)
        tag_font = _font("body", 38)
        url_font = _font("mono", 30)

        _draw_tracked_centered(draw, W // 2, 280, title, title_font, -1, WHITE)
        _draw_tracked_centered(
            draw,
            W // 2,
            380,
            "with prices, specs and a pick for every budget.",
            tag_font,
            0,
            (200, 200, 200),
        )
        _draw_tracked_centered(
            draw, W // 2, 520, "abvorn.com/" + (niche or "guides"), url_font, 0, WHITE
        )
        _draw_tracked_centered(
            draw,
            W // 2,
            620,
            "real research, not spec sheets",
            url_font,
            1,
            MUTED,
        )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert("RGB").save(out, quality=95)
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