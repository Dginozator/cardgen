"""Quick smoke test for the compositor — renders a test image without fonts or real data."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure parent is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from worker.compositor import UserData, compose

LAYOUT = {
    "canvas": {"width": 900, "height": 1200},
    "background": {"type": "gradient", "colors": ["#0f0c29", "#302b63", "#24243e"]},
    "zones": [
        {
            "type": "text",
            "x": 50, "y": 680, "w": 800, "h": 120,
            "field": "title",
            "font_size": 44,
            "font_weight": "bold",
            "color": "#FFFFFF",
            "align": "center",
            "vertical_align": "middle",
        },
        {
            "type": "bullets",
            "x": 80, "y": 830, "w": 740, "h": 330,
            "field": "bullets",
            "font_size": 30,
            "color": "#E0E0E0",
            "bullet_char": "✓",
            "line_spacing": 16,
            "icon_color": "#4FC3F7",
        },
    ],
}


def main() -> None:
    user_data = UserData(
        title="Беспроводные наушники Sony WH-1000XM5",
        bullets=[
            "Шумоподавление 30 часов",
            "Hi-Res Audio",
            "Быстрая зарядка 3 мин = 3 часа",
        ],
    )
    result = compose(LAYOUT, user_data, output_format="PNG")
    out = Path(__file__).resolve().parent / "test_output.png"
    out.write_bytes(result)
    print(f"✓ Smoke test passed — {len(result)} bytes → {out}")


if __name__ == "__main__":
    main()