"""SVG-based compositor: renders final infographic from SVG template + user data.

Template SVG convention:
  - Elements with id="zone_product_image" define where the product image goes
  - Elements with id="zone_text_{field}" define text fields
    (e.g. zone_text_title, zone_text_subtitle)
  - Elements with id="zone_bullets_{field}" define bullet containers
    (e.g. zone_bullets_features, zone_bullets_specs)
  - Elements with id="bg" or id="bg_*" define background
  - Placeholder text like {{title}} in <text> elements is replaced with real data
  - All styling (font, size, color, alignment) comes from native SVG attributes
"""

from __future__ import annotations

import io
import base64
import re
from dataclasses import dataclass, field
from typing import Any

from lxml import etree
from PIL import Image

# SVG namespace
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
NSMAP = {"svg": SVG_NS, "xlink": XLINK_NS}

# Prefixes for zone detection
ZONE_PRODUCT = "zone_product_image"
ZONE_TEXT_PREFIX = "zone_text_"
ZONE_BULLETS_PREFIX = "zone_bullets_"
BG_PREFIX = "bg"


@dataclass
class UserData:
    """Fields provided by the user."""
    title: str = ""
    bullets: list[str] = field(default_factory=list)
    product_image: bytes | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def get(self, field_name: str, default: str = "") -> str:
        """Get a field value by name."""
        if field_name == "title":
            return self.title
        if field_name == "bullets":
            return "\n".join(self.bullets)
        return self.extra.get(field_name, default)


def _find_all(elem: etree._Element, id_pattern: str) -> list[etree._Element]:
    """Find all elements whose id matches a prefix."""
    results = []
    for el in elem.iter():
        el_id = el.get("id", "")
        if el_id == id_pattern or el_id.startswith(id_pattern + "_") or el_id == id_pattern:
            results.append(el)
    return results


def _find_by_id(elem: etree._Element, target_id: str) -> etree._Element | None:
    """Find first element with given id."""
    for el in elem.iter():
        if el.get("id") == target_id:
            return el
    return None


def _find_zones(elem: etree._Element) -> dict[str, Any]:
    """Find all zone elements in the SVG."""
    zones: dict[str, Any] = {
        "product_image": None,
        "texts": {},
        "bullets": {},
        "background": None,
    }

    for el in elem.iter():
        el_id = el.get("id", "")
        if not el_id:
            continue

        if el_id == ZONE_PRODUCT:
            zones["product_image"] = el
        elif el_id.startswith(ZONE_TEXT_PREFIX):
            field_name = el_id[len(ZONE_TEXT_PREFIX):]
            zones["texts"][field_name] = el
        elif el_id.startswith(ZONE_BULLETS_PREFIX):
            field_name = el_id[len(ZONE_BULLETS_PREFIX):]
            zones["bullets"][field_name] = el
        elif el_id == BG_PREFIX or el_id.startswith(BG_PREFIX + "_"):
            if zones["background"] is None:
                zones["background"] = el

    return zones


def _parse_float(val: str | None, default: float = 0) -> float:
    """Parse a string to float, stripping units."""
    if val is None:
        return default
    val = re.sub(r"[a-zA-Z%]", "", val.strip())
    try:
        return float(val) if val else default
    except ValueError:
        return default


def _get_element_rect(el: etree._Element) -> dict[str, float]:
    """Get x, y, width, height from an SVG element."""
    return {
        "x": _parse_float(el.get("x"), 0),
        "y": _parse_float(el.get("y"), 0),
        "width": _parse_float(el.get("width"), 0),
        "height": _parse_float(el.get("height"), 0),
    }


def _image_to_base64_data_uri(image_bytes: bytes) -> str:
    """Convert image bytes to a base64 data URI."""
    img = Image.open(io.BytesIO(image_bytes))
    fmt = img.format or "PNG"
    mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(fmt, "image/png")
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


class SVGCompositor:
    """Compose an infographic from an SVG template and user data."""

    def __init__(self, svg_bytes: bytes | str) -> None:
        if isinstance(svg_bytes, str):
            svg_bytes = svg_bytes.encode("utf-8")
        self.tree = etree.fromstring(svg_bytes)
        self.zones = _find_zones(self.tree)

    # ------------------------------------------------------------------
    # Product image
    # ------------------------------------------------------------------

    def insert_product_image(
        self,
        image_bytes: bytes,
        fit: str = "contain",
        padding: float = 0,
    ) -> None:
        """Insert product image into the zone_product_image area."""
        zone = self.zones["product_image"]
        if zone is None:
            return

        rect = _get_element_rect(zone)
        if rect["width"] <= 0 or rect["height"] <= 0:
            return

        # Resize image to fit
        img = Image.open(io.BytesIO(image_bytes))
        inner_w = rect["width"] - 2 * padding
        inner_h = rect["height"] - 2 * padding
        if inner_w <= 0 or inner_h <= 0:
            inner_w, inner_h = rect["width"], rect["height"]

        img_w, img_h = img.size
        scale_w = inner_w / img_w
        scale_h = inner_h / img_h
        scale = min(scale_w, scale_h) if fit == "contain" else max(scale_w, scale_h)
        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)

        # Center in zone
        paste_x = rect["x"] + padding + (inner_w - new_w) / 2
        paste_y = rect["y"] + padding + (inner_h - new_h) / 2

        # If cover, crop
        if fit == "cover":
            img = img.crop((0, 0, min(new_w, int(inner_w)), min(new_h, int(inner_h))))

        # Encode resized image
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data_uri = _image_to_base64_data_uri(buf.getvalue())

        # Create SVG <image> element
        image_el = etree.SubElement(
            self.tree,
            f"{{{SVG_NS}}}image",
            {
                "href": data_uri,
                "x": str(paste_x),
                "y": str(paste_y),
                "width": str(new_w),
                "height": str(new_h),
            },
        )

        # Insert image right after the zone element's parent
        parent = zone.getparent()
        if parent is not None:
            idx = list(parent).index(zone)
            parent.remove(image_el)
            parent.insert(idx + 1, image_el)

    # ------------------------------------------------------------------
    # Text fields
    # ------------------------------------------------------------------

    def insert_text(self, field: str, text: str) -> None:
        """Replace text content in zone_text_{field} elements."""
        el = self.zones["texts"].get(field)
        if el is None:
            return

        # Replace {{field}} placeholders or entire text
        if el.text and "{{" in el.text:
            el.text = el.text.replace("{{" + field + "}}", text)
        else:
            el.text = text

        # Also check <tspan> children
        for tspan in el.iter(f"{{{SVG_NS}}}tspan"):
            if tspan.text and "{{" in tspan.text:
                tspan.text = tspan.text.replace("{{" + field + "}}", text)

    def insert_all_texts(self, user_data: UserData) -> None:
        """Insert all text fields from user data."""
        # Standard fields
        if user_data.title:
            self.insert_text("title", user_data.title)

        # Extra fields
        for key, value in user_data.extra.items():
            if isinstance(value, str):
                self.insert_text(key, value)

    # ------------------------------------------------------------------
    # Bullets
    # ------------------------------------------------------------------

    def insert_bullets(
        self,
        field: str,
        bullets: list[str],
        bullet_char: str = "✓",
        line_spacing: float = 0,
    ) -> None:
        """Generate bullet <text> elements in zone_bullets_{field}."""
        container = self.zones["bullets"].get(field)
        if container is None:
            return

        # Remove existing children (placeholder content)
        for child in list(container):
            container.remove(child)

        if not bullets:
            return

        # Get container position for offset
        cx = _parse_float(container.get("x"), 0)
        cy = _parse_float(container.get("y"), 0)

        # Try to read styling from the container element
        font_family = container.get("font-family", "Arial, sans-serif")
        font_size = _parse_float(container.get("font-size"), 28)
        text_color = container.get("fill", "#E0E0E0")

        # Bullet char styling — use a slightly different color if set
        bullet_color = container.get("data-bullet-color", "#4FC3F7")
        bullet_font_size = _parse_float(container.get("data-bullet-font-size"), font_size)

        # Line height
        if line_spacing <= 0:
            line_spacing = _parse_float(container.get("data-line-spacing"), 0)
        line_height = font_size * 1.4 + line_spacing

        for i, bullet_text in enumerate(bullets):
            y = cy + i * line_height

            # Bullet character
            bullet_el = etree.SubElement(
                container,
                f"{{{SVG_NS}}}text",
                {
                    "x": str(cx),
                    "y": str(y),
                    "font-family": font_family,
                    "font-size": str(bullet_font_size),
                    "font-weight": "bold",
                    "fill": bullet_color,
                },
            )
            bullet_el.text = bullet_char

            # Bullet text
            text_el = etree.SubElement(
                container,
                f"{{{SVG_NS}}}text",
                {
                    "x": str(cx + font_size * 1.2),
                    "y": str(y),
                    "font-family": font_family,
                    "font-size": str(font_size),
                    "fill": text_color,
                },
            )
            text_el.text = bullet_text

    def insert_all_bullets(self, user_data: UserData) -> None:
        """Insert bullet fields from user data."""
        if user_data.bullets:
            self.insert_bullets("features", user_data.bullets)
            # Also try generic "bullets" field
            self.insert_bullets("bullets", user_data.bullets)

        for key, value in user_data.extra.items():
            if isinstance(value, list):
                self.insert_bullets(key, value)

    # ------------------------------------------------------------------
    # Background
    # ------------------------------------------------------------------

    def insert_background_image(self, image_bytes: bytes) -> None:
        """Replace background zone with an image."""
        data_uri = _image_to_base64_data_uri(image_bytes)

        bg = self.zones["background"]
        if bg is not None:
            # Replace background element with image
            parent = bg.getparent()
            if parent is not None:
                image_el = etree.SubElement(
                    parent,
                    f"{{{SVG_NS}}}image",
                    {
                        "href": data_uri,
                        "x": "0",
                        "y": "0",
                        "width": "100%",
                        "height": "100%",
                        "preserveAspectRatio": "xMidYMid slice",
                    },
                )
                idx = list(parent).index(bg)
                parent.remove(image_el)
                parent.insert(idx, image_el)
                parent.remove(bg)
        else:
            # No background element found, prepend image to root
            image_el = etree.SubElement(
                self.tree,
                f"{{{SVG_NS}}}image",
                {
                    "href": data_uri,
                    "x": "0",
                    "y": "0",
                    "width": "100%",
                    "height": "100%",
                    "preserveAspectRatio": "xMidYMid slice",
                },
            )
            self.tree.insert(0, image_el)

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def to_svg_bytes(self) -> bytes:
        """Return the modified SVG as bytes."""
        return etree.tostring(self.tree, xml_declaration=True, encoding="UTF-8", pretty_print=True)

    def render(self, output_format: str = "PNG", dpi: float = 150) -> bytes:
        """Render SVG to image bytes using CairoSVG + Pillow."""
        svg_data = self.to_svg_bytes()

        try:
            import cairosvg
            png_data = cairosvg.svg2png(bytestring=svg_data, dpi=dpi)
        except ImportError:
            raise RuntimeError(
                "cairosvg is required for rendering. Install it with: pip install cairosvg"
            )

        if output_format.upper() in ("JPEG", "JPG"):
            img = Image.open(io.BytesIO(png_data)).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=95)
            return buf.getvalue()
        elif output_format.upper() == "WEBP":
            img = Image.open(io.BytesIO(png_data)).convert("RGBA")
            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=95)
            return buf.getvalue()
        else:
            return png_data

    # ------------------------------------------------------------------
    # Info extraction
    # ------------------------------------------------------------------

    def get_canvas_size(self) -> tuple[int, int]:
        """Extract canvas width/height from SVG."""
        w = _parse_float(self.tree.get("width"), 900)
        h = _parse_float(self.tree.get("height"), 1200)
        return int(w), int(h)

    def validate(self) -> list[str]:
        """Validate the template SVG, return list of warnings."""
        warnings = []
        if self.zones["product_image"] is None:
            warnings.append("Missing zone_product_image element")
        if not self.zones["texts"] and not self.zones["bullets"]:
            warnings.append("No zone_text_* or zone_bullets_* elements found")
        return warnings


def compose(
    svg_bytes: bytes,
    user_data: UserData,
    bg_image_data: bytes | None = None,
    output_format: str = "PNG",
) -> bytes:
    """
    High-level compose function: SVG template + user data → image bytes.
    """
    compositor = SVGCompositor(svg_bytes)

    # Insert product image
    if user_data.product_image:
        compositor.insert_product_image(user_data.product_image)

    # Insert text fields
    compositor.insert_all_texts(user_data)

    # Insert bullets
    compositor.insert_all_bullets(user_data)

    # Insert AI background
    if bg_image_data:
        compositor.insert_background_image(bg_image_data)

    return compositor.render(output_format)