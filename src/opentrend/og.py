"""Dynamic Open Graph / social card rendering.

Renders 1200x630 PNG cards on the fly with Pillow, using the vendored IBM Plex
Mono fonts so cards match the site's monospace branding. Cards are only meant
for public, shareable pages (the home/default card and public project
dashboards).
"""

from __future__ import annotations

import io
import logging
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_VENDOR = Path(__file__).parent / "static" / "vendor"
_FONT_500 = str(_VENDOR / "ibm-plex-mono-og.ttf")
_FONT_600 = str(_VENDOR / "ibm-plex-mono-600-og.ttf")

# Card dimensions - the canonical Open Graph image size.
WIDTH, HEIGHT = 1200, 630
_PAD = 72

# Logo geometry. Shared between _draw_logo and _draw_wordmark so the wordmark's
# text offset tracks the logo size instead of hardcoding it.
_LOGO_CELL = 13
_LOGO_GAP = 5

# Palette mirrors src/opentrend/static/css/style.css :root tokens.
_BG = (17, 17, 22)  # --bg #111116
_FG_BRIGHT = (240, 240, 244)  # --fg-bright
_FG_DIM = (144, 144, 160)  # --fg-dim
_FG_FAINT = (106, 106, 122)  # --fg-faint
_TEAL = (94, 234, 212)  # accent-teal #5EEAD4


@lru_cache(maxsize=16)
def _font(weight: int, size: int) -> ImageFont.FreeTypeFont:
    path = _FONT_600 if weight >= 600 else _FONT_500
    return ImageFont.truetype(path, size)


def _format_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def _text_width(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont
) -> float:
    return draw.textlength(text, font=font)


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    weight: int,
    max_size: int,
    min_size: int,
    max_width: int,
) -> tuple[str, ImageFont.FreeTypeFont]:
    """Shrink font to fit max_width; ellipsize at min_size if still too wide."""
    size = max_size
    while size > min_size:
        font = _font(weight, size)
        if _text_width(draw, text, font) <= max_width:
            return text, font
        size -= 4
    font = _font(weight, min_size)
    if _text_width(draw, text, font) <= max_width:
        return text, font
    # Ellipsize
    ellipsis = "…"
    while text and _text_width(draw, text + ellipsis, font) > max_width:
        text = text[:-1]
    return text + ellipsis, font


def _draw_logo(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    cell: int = _LOGO_CELL,
    gap: int = _LOGO_GAP,
) -> None:
    """The 2x2 teal square logo mark."""
    for row in range(2):
        for col in range(2):
            x0 = x + col * (cell + gap)
            y0 = y + row * (cell + gap)
            draw.rectangle([x0, y0, x0 + cell, y0 + cell], fill=_TEAL)


def _draw_wordmark(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    _draw_logo(draw, x, y + 4)
    logo_w = 2 * _LOGO_CELL + _LOGO_GAP
    tx = x + logo_w + 16
    font = _font(600, 34)
    draw.text((tx, y), "opentrend", font=font, fill=_TEAL)
    w = _text_width(draw, "opentrend", font)
    draw.text((tx + w, y), ".dev", font=font, fill=_FG_DIM)


def _new_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (WIDTH, HEIGHT), _BG)
    draw = ImageDraw.Draw(img)
    # Teal accent bar along the top edge.
    draw.rectangle([0, 0, WIDTH, 6], fill=_TEAL)
    return img, draw


def _encode(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_project_card(
    *,
    display_name: str,
    repo: str,
    reach: int,
    stars: int,
    downloads: int,
    packages: int,
    license: str | None = None,
    version: str | None = None,
) -> bytes:
    img, draw = _new_canvas()
    _draw_wordmark(draw, _PAD, _PAD)

    # Project name - large, fit to width.
    name_y = _PAD + 96
    name, name_font = _fit_text(draw, display_name, 600, 92, 52, WIDTH - 2 * _PAD)
    draw.text((_PAD, name_y), name, font=name_font, fill=_FG_BRIGHT)

    # Subline: repo · license · version
    sub_parts = [repo]
    if license:
        sub_parts.append(license)
    if version:
        sub_parts.append(version)
    sub = "  ·  ".join(sub_parts)
    sub_text, sub_font = _fit_text(draw, sub, 500, 32, 22, WIDTH - 2 * _PAD)
    draw.text((_PAD, name_y + 108), sub_text, font=sub_font, fill=_FG_DIM)

    # Stats row near the bottom.
    stats = [
        ("REACH", _format_number(reach), _TEAL),
        ("STARS", _format_number(stars), _FG_BRIGHT),
        ("DOWNLOADS/MO", _format_number(downloads), _FG_BRIGHT),
        ("PACKAGES", str(packages), _FG_BRIGHT),
    ]
    num_font = _font(600, 68)
    label_font = _font(500, 24)
    stat_y = HEIGHT - _PAD - 96
    col_w = (WIDTH - 2 * _PAD) // len(stats)
    for i, (label, value, color) in enumerate(stats):
        cx = _PAD + i * col_w
        draw.text((cx, stat_y), value, font=num_font, fill=color)
        draw.text((cx, stat_y + 80), label, font=label_font, fill=_FG_FAINT)

    return _encode(img)


def render_default_card() -> bytes:
    img, draw = _new_canvas()
    _draw_wordmark(draw, _PAD, _PAD)

    headline = ["Open source adoption,", "beyond the star count."]
    h_font = _font(600, 76)
    y = _PAD + 130
    for line in headline:
        draw.text((_PAD, y), line, font=h_font, fill=_FG_BRIGHT)
        y += 92

    sub = "GitHub · package registries · 25+ OS distributions"
    sub_text, sub_font = _fit_text(draw, sub, 500, 34, 24, WIDTH - 2 * _PAD)
    draw.text((_PAD, y + 24), sub_text, font=sub_font, fill=_FG_DIM)

    return _encode(img)


def render_fallback_card() -> bytes:
    """Minimal, font-free card for when normal rendering fails.

    Draws only the background, accent bar, and the (text-free) logo mark, so it
    cannot fail on a missing or broken font. Lets the og.png routes always
    return a valid image instead of an HTML error page.
    """
    img, draw = _new_canvas()
    _draw_logo(draw, _PAD, _PAD, cell=64, gap=24)
    return _encode(img)


def render_or_fallback(
    render, *args, label: str = "card", **kwargs
) -> tuple[bytes, bool]:
    """Render a card, falling back to a font-free placeholder on any error.

    Returns ``(png_bytes, failed)`` so the caller can avoid caching a failure.
    Logs the exception with context (nothing else does - a bare render error
    would otherwise surface as a generic HTML 500 under an image/png route).
    """
    try:
        return render(*args, **kwargs), False
    except Exception:
        logger.exception("OG card render failed (%s); serving fallback", label)
        return render_fallback_card(), True
