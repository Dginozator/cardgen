"""Pillow-based compositor: renders final infographic from layout JSON + user data.

Layout JSON schema:
{
  "canvas": {"width": 900, "height": 1200},
  "background": {"type": "gradient"|"solid"|"image", ...},
  "zones": [
    {
      "type": "product_image",
      "x": 50, "y": 50, "w": 800, "h": 700,
      "fit": "contain"|"cover",
      "padding": 20,
      "remove_bg": true
    },
    {
      "type": "text",
      "x": 50, "y": 800, "w": 800, "h": 100,
      "field": "title",
      "font_size": 48,
      "font_weight": "bold",
      "color": "#FFFFFF",
      "align": "center",
      "vertical_align": "middle"
    },
    {
      "type": "bullets",
      "x": 50, "y": 920, "w": 800, "h": 250,
      "field": "bullets",
      "font_size": 32,
      "color": "#FFFFFF",
      "bullet_char": "✓",
      "line_spacing": 12,
      "icon_color": "#4FC3F7"
    }
  ]
}
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ZoneRect:
    """Integer pixel rectangle."""
    x: int
    y: int
    w: int
    h: int

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.w, self.y + self.h)

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)


@dataclass
class UserData:
    """Fields provided by the user."""
    title: str = ""
    bullets: list[str] = field(default_factory=list)
    product_image: bytes | None = None
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

_FONT_DIR = Path(__file__).resolve().parent / "fonts"

_DEFAULT_FONTS = [
    "Inter-Bold.ttf",
    "Inter-Regular.ttf",
    "DejaVuSans-Bold.ttf",
    "DejaVuSans.ttf",
    "arial.ttf",
    "Arial Bold.ttf",
]


def _find_font(bold: bool = False) -> Path | None:
    candidates = _DEFAULT_FONTS[:2] if bold else _DEFAULT_FONTS[2:4]
    for name in candidates:
        p = _FONT_DIR / name
        if p.is_file():
            return p
    # fallback: any ttf in fonts dir
    for p in _FONT_DIR.glob("*.ttf"):
        if bold and "bold" in p.name.lower():
            return p
        if not bold and "bold" not in p.name.lower():
            return p
    return None


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = _find_font(bold)
    if path:
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            pass
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Background renderers
# ---------------------------------------------------------------------------

def _render_gradient(canvas: Image.Image, spec: dict[str, Any]) -> None:
    """Draw a linear gradient top-to-bottom."""
    draw = ImageDraw.Draw(canvas)
    colors = spec.get("colors", ["#1a1a2e", "#16213e", "#0f3460"])
    h = canvas.height
    steps = len(colors) - 1
    if steps <= 0:
        draw.rectangle([0, 0, canvas.width, canvas.height], fill=colors[0])
        return
    band_h = max(1, h // steps)
    for i in range(steps):
        c_start = _parse_color(colors[i])
        c_end = _parse_color(colors[i + 1])
        y0 = i * band_h
        y1 = min((i + 1) * band_h + 1, h)
        for y in range(y0, y1):
            t = (y - y0) / max(1, y1 - y0 - 1)
            r = int(c_start[0] + (c_end[0] - c_start[0]) * t)
            g = int(c_start[1] + (c_end[1] - c_start[1]) * t)
            b = int(c_start[2] + (c_end[2] - c_start[2]) * t)
            draw.line([(0, y), (canvas.width, y)], fill=(r, g, b))


def _render_solid(canvas: Image.Image, spec: dict[str, Any]) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, canvas.width, canvas.height], fill=spec.get("color", "#FFFFFF"))


def _render_bg_image(canvas: Image.Image, data: bytes) -> None:
    bg = Image.open(io.BytesIO(data)).convert("RGBA")
    bg = bg.resize((canvas.width, canvas.height), Image.LANCZOS)
    canvas.paste(bg, (0, 0))


def render_background(canvas: Image.Image, spec: dict[str, Any], bg_data: bytes | None = None) -> None:
    bg_type = spec.get("type", "gradient")
    if bg_type == "image" and bg_data:
        _render_bg_image(canvas, bg_data)
    elif bg_type == "solid":
        _render_solid(canvas, spec)
    else:
        _render_gradient(canvas, spec)


# ---------------------------------------------------------------------------
# Zone renderers
# ---------------------------------------------------------------------------

def _parse_color(c: str) -> tuple[int, int, int, int]:
    """Parse CSS color string to RGBA tuple."""
    c = c.strip()
    if c.startswith("#"):
        hex_c = c[1:]
        if len(hex_c) == 3:
            hex_c = "".join(ch * 2 for ch in hex_c)
        r, g, b = int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)
        return (r, g, b, 255)
    return (255, 255, 255, 255)


def _fit_image(img: Image.Image, rect: ZoneRect, fit: str = "contain", padding: int = 0) -> Image.Image:
    """Resize and optionally crop image to fit in rect."""
    inner_w = rect.w - 2 * padding
    inner_h = rect.h - 2 * padding
    if inner_w <= 0 or inner_h <= 0:
        return img

    img_w, img_h = img.size
    scale_w = inner_w / img_w
    scale_h = inner_h / img_h

    if fit == "cover":
        scale = max(scale_w, scale_h)
    else:  # contain
        scale = min(scale_w, scale_h)

    new_w = max(1, int(img_w * scale))
    new_h = max(1, int(img_h * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)

    if fit == "cover":
        left = max(0, (new_w - inner_w) // 2)
        top = max(0, (new_h - inner_h) // 2)
        img = img.crop((left, top, left + inner_w, top + inner_h))

    return img


def _render_product_image(
    canvas: Image.Image,
    zone: dict[str, Any],
    user_data: UserData,
) -> None:
    """Place the product image into the zone."""
    if not user_data.product_image:
        return

    rect = ZoneRect(**{k: zone[k] for k in ("x", "y", "w", "h")})
    padding = zone.get("padding", 0)
    fit = zone.get("fit", "contain")

    try:
        img = Image.open(io.BytesIO(user_data.product_image)).convert("RGBA")
    except Exception:
        return

    img = _fit_image(img, rect, fit=fit, padding=padding)

    # Center the fitted image in the zone
    paste_x = rect.x + padding + (rect.w - 2 * padding - img.width) // 2
    paste_y = rect.y + padding + (rect.h - 2 * padding - img.height) // 2

    # Handle transparency
    if img.mode == "RGBA":
        canvas.paste(img, (paste_x, paste_y), img)
    else:
        canvas.paste(img, (paste_x, paste_y))


def _render_text_zone(
    canvas: Image.Image,
    zone: dict[str, Any],
    user_data: UserData,
) -> None:
    """Render a single text field."""
    field_name = zone.get("field", "title")
    text = getattr(user_data, field_name, "") or user_data.extra.get(field_name, "")
    if not text:
        return

    rect = ZoneRect(**{k: zone[k] for k in ("x", "y", "w", "h")})
    font_size = zone.get("font_size", 36)
    bold = zone.get("font_weight", "normal") == "bold"
    color = _parse_color(zone.get("color", "#FFFFFF"))
    align = zone.get("align", "center")
    valign = zone.get("vertical_align", "middle")

    font = _load_font(font_size, bold)

    # Auto-shrink font if text doesn't fit
    draw = ImageDraw.Draw(canvas)
    for _ in range(10):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        if text_w <= rect.w:
            break
        font_size = max(12, font_size - 4)
        font = _load_font(font_size, bold)

    # Calculate position
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    if align == "center":
        tx = rect.x + (rect.w - text_w) // 2
    elif align == "right":
        tx = rect.x + rect.w - text_w
    else:
        tx = rect.x

    if valign == "middle":
        ty = rect.y + (rect.h - text_h) // 2
    elif valign == "bottom":
        ty = rect.y + rect.h - text_h
    else:
        ty = rect.y

    draw.text((tx, ty), text, fill=color[:3], font=font)


def _render_bullets_zone(
    canvas: Image.Image,
    zone: dict[str, Any],
    user_data: UserData,
) -> None:
    """Render bullet points."""
    bullets = user_data.bullets
    if not bullets:
        return

    rect = ZoneRect(**{k: zone[k] for k in ("x", "y", "w", "h")})
    font_size = zone.get("font_size", 28)
    color = _parse_color(zone.get("color", "#FFFFFF"))
    bullet_char = zone.get("bullet_char", "✓")
    line_spacing = zone.get("line_spacing", 12)
    icon_color = _parse_color(zone.get("icon_color", "#4FC3F7"))

    font = _load_font(font_size, bold=False)
    bullet_font = _load_font(font_size, bold=True)
    draw = ImageDraw.Draw(canvas)

    # Measure line height
    bbox = draw.textbbox((0, 0), "Ay", font=font)
    line_h = (bbox[3] - bbox[1]) + line_spacing

    y = rect.y
    for bullet_text in bullets:
        if y + line_h > rect.y + rect.h:
            break  # no more space

        # Draw bullet char
        draw.text((rect.x, y), bullet_char, fill=icon_color[:3], font=bullet_font)
        bb = draw.textbbox((0, 0), bullet_char, font=bullet_font)
        bullet_w = bb[2] - bb[0] + 12

        # Draw text (auto-shrink if needed)
        current_font = font
        for _ in range(8):
            tb = draw.textbbox((0, 0), bullet_text, font=current_font)
            tw = tb[2] - tb[0]
            if tw <= rect.w - bullet_w:
                break
            smaller = max(12, current_font.size - 3)
            current_font = _load_font(smaller, bold=False)

        draw.text((rect.x + bullet_w, y), bullet_text, fill=color[:3], font=current_font)
        y += line_h


def _render_zone(
    canvas: Image.Image,
    zone: dict[str, Any],
    user_data: UserData,
) -> None:
    zone_type = zone.get("type", "")
    if zone_type == "product_image":
        _render_product_image(canvas, zone, user_data)
    elif zone_type == "text":
        _render_text_zone(canvas, zone, user_data)
    elif zone_type == "bullets":
        _render_bullets_zone(canvas, zone, user_data)


# ---------------------------------------------------------------------------
# Main compositor
# ---------------------------------------------------------------------------

def compose(
    layout: dict[str, Any],
    user_data: UserData,
    bg_image_data: bytes | None = None,
    output_format: str = "PNG",
) -> bytes:
    """
    Render the final infographic image from layout + user data.

    Returns image bytes in the specified format.
    """
    canvas_spec = layout.get("canvas", {"width": 900, "height": 1200})
    cw = canvas_spec.get("width", 900)
    ch = canvas_spec.get("height", 1200)

    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))

    # Background
    bg_spec = layout.get("background", {"type": "gradient", "colors": ["#1a1a2e", "#0f3460"]})
    render_background(canvas, bg_spec, bg_image_data)

    # Zones
    for zone in layout.get("zones", []):
        _render_zone(canvas, zone, user_data)

    # Convert to output format
    buf = io.BytesIO()
    if output_format.upper() == "JPEG" or output_format.upper() == "JPG":
        rgb = Image.new("RGB", canvas.size, (255, 255, 255))
        rgb.paste(canvas, mask=canvas.split()[3] if canvas.mode == "RGBA" else None)
        rgb.save(buf, format="JPEG", quality=95)
    elif output_format.upper() == "WEBP":
        canvas.save(buf, format="WEBP", quality=95)
    else:
        canvas.save(buf, format="PNG")

    return buf.getvalue()