"""Create example SVG templates."""
from pathlib import Path

DIR = Path(__file__).parent

# 1. Infographic 3:4 (900x1200)
(DIR / "infographic-3x4.svg").write_text("""\
<?xml version="1.0" encoding="UTF-8"?>
<svg width="900" height="1200" viewBox="0 0 900 1200" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg_gradient" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#0f0c29"/>
      <stop offset="50%" stop-color="#302b63"/>
      <stop offset="100%" stop-color="#24243e"/>
    </linearGradient>
  </defs>
  <rect id="bg" fill="url(#bg_gradient)" width="900" height="1200"/>
  <circle cx="450" cy="350" r="320" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="2"/>
  <rect id="zone_product_image" x="100" y="50" width="700" height="600" fill="transparent"/>
  <text id="zone_text_title" x="450" y="730" font-family="Arial, sans-serif" font-size="44" font-weight="bold" fill="#FFFFFF" text-anchor="middle">{{title}}</text>
  <text id="zone_text_subtitle" x="450" y="785" font-family="Arial, sans-serif" font-size="22" fill="#9CA3AF" text-anchor="middle"></text>
  <line x1="200" y1="810" x2="700" y2="810" stroke="rgba(79,195,247,0.3)" stroke-width="1"/>
  <g id="zone_bullets_features" x="80" y="840" font-family="Arial, sans-serif" font-size="30" fill="#E0E0E0" data-bullet-color="#4FC3F7" data-line-spacing="16"></g>
</svg>
""", encoding="utf-8")

# 2. Infographic 1:1 (900x900)
(DIR / "infographic-1x1.svg").write_text("""\
<?xml version="1.0" encoding="UTF-8"?>
<svg width="900" height="900" viewBox="0 0 900 900" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg_gradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1a1a2e"/>
      <stop offset="50%" stop-color="#16213e"/>
      <stop offset="100%" stop-color="#0f3460"/>
    </linearGradient>
  </defs>
  <rect id="bg" fill="url(#bg_gradient)" width="900" height="900"/>
  <rect id="zone_product_image" x="100" y="50" width="700" height="450" fill="transparent"/>
  <text id="zone_text_title" x="450" y="560" font-family="Arial, sans-serif" font-size="38" font-weight="bold" fill="#FFFFFF" text-anchor="middle">{{title}}</text>
  <line x1="150" y1="590" x2="750" y2="590" stroke="rgba(79,195,247,0.3)" stroke-width="1"/>
  <g id="zone_bullets_features" x="100" y="620" font-family="Arial, sans-serif" font-size="26" fill="#E0E0E0" data-bullet-color="#4FC3F7" data-line-spacing="12"></g>
</svg>
""", encoding="utf-8")

# 3. Simple product slide 3:4 (AI background)
(DIR / "product-slide-3x4.svg").write_text("""\
<?xml version="1.0" encoding="UTF-8"?>
<svg width="900" height="1200" viewBox="0 0 900 1200" xmlns="http://www.w3.org/2000/svg">
  <!-- AI background - will be replaced by generated image -->
  <rect id="bg_ai" fill="#1a1a2e" width="900" height="1200"/>
  <!-- Product takes full canvas with padding -->
  <rect id="zone_product_image" x="50" y="50" width="800" height="1100" fill="transparent"/>
</svg>
""", encoding="utf-8")

print("Created 3 SVG templates in", DIR)